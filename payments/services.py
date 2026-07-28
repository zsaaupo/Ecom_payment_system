"""
PaymentService orchestrates the full payment lifecycle:

    1. User selects products -> creates order.
    2. User chooses the payment provider.
    3. System initiates payment via provider strategy.
    4. Provider confirms or fails payment (via callback or webhook).
    5. Order status is updated accordingly.
    6. Stock is reduced atomically upon successful payment.
"""
import logging

from django.db import transaction

from orders.models import Order
from orders.services import OrderService
from products.services import InsufficientStockError, ProductService

from .models import Payment
from .strategies import PaymentContext, PaymentProviderError

logger = logging.getLogger("payments")


class PaymentService:

    @staticmethod
    def initiate_payment(order: Order, provider: str) -> Payment:
        """Step 2-3 of the order flow: create the Payment record and ask
        the provider (via its Strategy) to start the payment."""
        context = PaymentContext(provider)
        result = context.initiate(order)

        payment = Payment.objects.create(
            order=order,
            provider=provider,
            transaction_id=result["transaction_id"],
            status=Payment.Status.PENDING,
            amount=order.total_amount,
            raw_response=result.get("raw_response", {}),
        )
        logger.info("Payment initiated: order=%s provider=%s txn=%s", order.id, provider, payment.transaction_id)
        # Extra provider-specific data (client_secret, bkash_url, ...) is
        # returned to the caller (view) but not persisted verbatim, since
        # it's short-lived and provider-specific.
        return payment, result

    @staticmethod
    @transaction.atomic
    def confirm_payment(payment: Payment, payload=None) -> Payment:
        """Steps 4-6 of the order flow. Confirms with the provider, then
        atomically updates the Payment, the Order, and product stock."""
        if payment.status in (Payment.Status.SUCCESS, Payment.Status.FAILED):
            return payment

        context = PaymentContext(payment.provider)
        try:
            result = context.confirm(payment.transaction_id, payload)
        except PaymentProviderError as exc:
            logger.error("Payment confirmation failed: %s", exc)
            payment.status = Payment.Status.FAILED
            payment.raw_response = {"error": str(exc)}
            payment.save(update_fields=["status", "raw_response", "updated_at"])
            return payment

        return PaymentService._apply_result(payment, result)

    @staticmethod
    @transaction.atomic
    def _apply_result(payment: Payment, result: dict) -> Payment:
        """
        Shared step 5-6 logic: persist the (already-determined) outcome of
        a payment attempt onto Payment/Order/stock. Used both by
        confirm_payment() (which just called the provider) and by
        handle_stripe_event() (which trusts the signature-verified webhook
        payload directly, with no extra round-trip to Stripe).
        """
        payment.status = result["status"]
        payment.raw_response = result.get("raw_response", payment.raw_response)
        payment.save(update_fields=["status", "raw_response", "updated_at"])

        order = payment.order
        if payment.status == Payment.Status.SUCCESS:
            OrderService.mark_paid(order)
            for item in order.items.select_related("product").all():
                try:
                    ProductService.reduce_stock(item.product_id, item.quantity)
                except InsufficientStockError as exc:
                    # Payment already succeeded on the provider's side; we log
                    # loudly for manual reconciliation rather than silently
                    # failing, since refunding is outside this system's scope.
                    logger.error("Stock reduction failed after successful payment: %s", exc)
        elif payment.status == Payment.Status.FAILED:
            OrderService.cancel(order)

        logger.info("Payment confirmed: order=%s provider=%s status=%s", order.id, payment.provider, payment.status)
        return payment

    @staticmethod
    def handle_stripe_event(event: dict):
        """
        Handles payment_intent.succeeded / payment_intent.payment_failed Stripe webhook events.
        """
        event_type = event.get("type")
        intent = event.get("data", {}).get("object", {})
        transaction_id = intent.get("id")
        if not transaction_id:
            return None

        try:
            payment = Payment.objects.select_related("order").get(
                transaction_id=transaction_id, provider=Payment.Provider.STRIPE
            )
        except Payment.DoesNotExist:
            logger.warning("Stripe webhook for unknown transaction_id=%s", transaction_id)
            return None

        if event_type == "payment_intent.succeeded":
            return PaymentService._apply_result(payment, {"status": Payment.Status.SUCCESS, "raw_response": event})
        elif event_type == "payment_intent.payment_failed":
            return PaymentService._apply_result(payment, {"status": Payment.Status.FAILED, "raw_response": event})
        return payment

    @staticmethod
    def handle_bkash_event(event: dict):
        """
        Handles bKash IPN / callback webhook event.
        """
        payment_id = event.get("payment_id")
        status_val = event.get("status")

        if not payment_id:
            return None

        try:
            payment = Payment.objects.select_related("order").get(
                transaction_id=payment_id, provider=Payment.Provider.BKASH
            )
        except Payment.DoesNotExist:
            logger.warning("bKash webhook for unknown payment_id=%s", payment_id)
            return None

        if status_val in ("cancel", "failure"):
            return PaymentService._apply_result(payment, {"status": Payment.Status.FAILED, "raw_response": event})
        else:
            return PaymentService.confirm_payment(payment)

    @staticmethod
    def query_payment(payment: Payment):
        """Queries payment status from the payment provider."""
        context = PaymentContext(payment.provider)
        result = context.query(payment.transaction_id)
        payment.status = result["status"]
        payment.raw_response = result.get("raw_response", payment.raw_response)
        payment.save(update_fields=["status", "raw_response", "updated_at"])
        return payment
