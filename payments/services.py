"""Payment transitions shared by confirmations, queries and verified callbacks."""
import logging
from collections import Counter
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from orders.models import Order
from products.models import Product
from products.services import InsufficientStockError, ProductService
from .models import Payment
from .strategies import PaymentContext

logger = logging.getLogger('payments')


class PaymentService:
    @staticmethod
    def _quantities(order):
        quantities = Counter()
        for item in order.items.all():
            quantities[item.product_id] += item.quantity
        return quantities

    @staticmethod
    def _reserve(order):
        quantities = PaymentService._quantities(order)
        if not quantities or order.total_amount <= 0:
            raise ValidationError('An order must contain items and have a positive total.')
        for product_id, quantity in sorted(quantities.items()):
            updated = Product.objects.filter(
                pk=product_id, status=Product.Status.ACTIVE, stock__gte=quantity
            ).update(stock=F('stock') - quantity)
            if not updated:
                raise ValidationError('An item is unavailable or has insufficient stock. Review your order.')
        order.stock_reserved = True
        order.save(update_fields=['stock_reserved'])

    @staticmethod
    @transaction.atomic
    def initiate_payment(order, provider):
        # IMMEDIATE transactions serialize SQLite writers; row locks serve other backends.
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status != Order.Status.PENDING:
            raise ValidationError('Only pending orders can start a payment.')
        existing = order.payments.exclude(status=Payment.Status.FAILED).first()
        if existing:
            if existing.provider != provider:
                raise ValidationError('This order already has a payment with another provider.')
            result = dict(existing.raw_response)
            if provider == 'stripe':
                from django.conf import settings
                result['publishable_key'] = settings.STRIPE_PUBLISHABLE_KEY
            else:
                result['bkash_url'] = result.get('bkashURL')
            return existing, result
        if not order.stock_reserved:
            PaymentService._reserve(order)
        result = PaymentContext(provider).initiate(order)
        payment = Payment.objects.create(
            order=order, provider=provider, transaction_id=result['transaction_id'],
            status=Payment.Status.PENDING, amount=order.total_amount,
            raw_response=result.get('raw_response', {}),
        )
        return payment, result

    @staticmethod
    def confirm_payment(payment, payload=None):
        payment.refresh_from_db()
        if payment.status == Payment.Status.SUCCESS:
            return payment
        # An API outage is an unknown outcome, not a failed payment. Let callers retry.
        result = PaymentContext(payment.provider).confirm(payment.transaction_id, payload)
        return PaymentService._apply_result(payment, result)

    @staticmethod
    @transaction.atomic
    def _apply_result(payment, result):
        # Always reload under locks: callers may hold a stale pre-webhook instance.
        order = Order.objects.select_for_update().get(pk=payment.order_id)
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.status == Payment.Status.SUCCESS:
            return payment
        new_status = result['status']
        if payment.status == Payment.Status.FAILED and new_status == Payment.Status.PENDING:
            return payment
        if new_status not in Payment.Status.values:
            raise ValidationError('Invalid payment status.')
        payment.status = new_status
        payment.raw_response = {**payment.raw_response, **result.get('raw_response', {})}
        payment.save(update_fields=['status', 'raw_response', 'updated_at'])
        if new_status == Payment.Status.SUCCESS:
            if order.status == Order.Status.PAID:
                order.needs_review = True
            else:
                if not order.stock_reserved:
                    try:
                        # Legacy orders may predate reservations. Deduct all lines or none.
                        with transaction.atomic():
                            for product_id, quantity in sorted(PaymentService._quantities(order).items()):
                                ProductService.reduce_stock(product_id, quantity)
                    except InsufficientStockError:
                        order.needs_review = True
                        logger.error('Paid order %s requires stock/refund review', order.pk)
                order.status = Order.Status.PAID
                order.stock_reserved = False
        elif new_status == Payment.Status.FAILED and order.status != Order.Status.PAID:
            if order.stock_reserved:
                for product_id, quantity in PaymentService._quantities(order).items():
                    Product.objects.filter(pk=product_id).update(stock=F('stock') + quantity)
                order.stock_reserved = False
            order.status = Order.Status.CANCELED
        order.save(update_fields=['status', 'stock_reserved', 'needs_review', 'updated_at'])
        return payment

    @staticmethod
    def handle_stripe_event(event):
        intent = event.get('data', {}).get('object', {})
        payment = Payment.objects.filter(transaction_id=intent.get('id'), provider='stripe').first()
        if payment is None:
            return None
        event_type = event.get('type')
        if event_type == 'payment_intent.succeeded':
            return PaymentService._apply_result(payment, {'status': 'success', 'raw_response': event})
        if event_type == 'payment_intent.canceled':
            return PaymentService._apply_result(payment, {'status': 'failed', 'raw_response': event})
        if event_type == 'payment_intent.payment_failed':
            # A declined attempt leaves the same PaymentIntent open for another card.
            return PaymentService._apply_result(payment, {'status': 'pending', 'raw_response': intent})
        return payment

    @staticmethod
    def handle_bkash_event(event):
        payment = Payment.objects.filter(transaction_id=event.get('payment_id'), provider='bkash').first()
        if payment is None:
            return None
        # Browser-supplied cancellation is untrusted; query bKash before changing data.
        if event.get('status') in ('cancel', 'failure'):
            return PaymentService.query_payment(payment)
        return PaymentService.confirm_payment(payment)

    @staticmethod
    def query_payment(payment):
        payment.refresh_from_db()
        if payment.status == Payment.Status.SUCCESS:
            return payment
        result = PaymentContext(payment.provider).query(payment.transaction_id)
        return PaymentService._apply_result(payment, result)
