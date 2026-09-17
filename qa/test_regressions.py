from decimal import Decimal
from unittest.mock import patch

import requests
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from orders.models import Order, OrderItem
from payments.models import Payment
from payments.services import PaymentService
from payments.strategies import BkashPaymentStrategy, StripePaymentStrategy, PaymentProviderError
from products.models import Category, Product
from users.models import User
from users.services import UserService


class CheckoutRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='qa', email='qa@example.com', password='Test-password-135!')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.product = Product.objects.create(name='QA product', sku='QA', price=Decimal('12.50'), stock=5)

    def order(self):
        order = Order.objects.create(user=self.user, total_amount=Decimal('25.00'))
        OrderItem.objects.create(order=order, product=self.product, quantity=2, price='12.50', subtotal='25.00')
        return order

    def payment(self, provider='stripe'):
        return Payment.objects.create(order=self.order(), provider=provider, transaction_id=f'txn-{Payment.objects.count()}', amount='25.00')

    def test_empty_order_rejected(self):
        response = self.client.post('/api/orders/', {'items': []}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_invalid_later_line_rolls_back_entire_order(self):
        response = self.client.post('/api/orders/', {'items': [
            {'product_id': self.product.pk, 'quantity': 1}, {'product_id': 99999, 'quantity': 1}
        ]}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)

    def test_duplicate_lines_cannot_bypass_stock_check(self):
        response = self.client.post('/api/orders/', {'items': [
            {'product_id': self.product.pk, 'quantity': 3}, {'product_id': self.product.pk, 'quantity': 3}
        ]}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_duplicate_success_deducts_stock_once(self):
        payment = self.payment()
        result = {'status': 'success'}
        PaymentService._apply_result(payment, result)
        PaymentService._apply_result(payment, result)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_late_failure_cannot_cancel_paid_order(self):
        payment = self.payment()
        PaymentService._apply_result(payment, {'status': 'success'})
        PaymentService._apply_result(payment, {'status': 'failed'})
        payment.refresh_from_db()
        payment.order.refresh_from_db()
        self.assertEqual(payment.status, 'success')
        self.assertEqual(payment.order.status, 'paid')

    @patch.object(BkashPaymentStrategy, 'query', return_value={'status': 'success'})
    def test_query_success_updates_order_and_stock(self, _):
        payment = self.payment('bkash')
        PaymentService.query_payment(payment)
        payment.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(payment.order.status, 'paid')
        self.assertEqual(self.product.stock, 3)

    @patch.object(StripePaymentStrategy, 'confirm', side_effect=PaymentProviderError('temporary outage'))
    def test_provider_outage_keeps_payment_retryable(self, _):
        payment = self.payment()
        response = self.client.post(f'/api/payments/{payment.pk}/confirm/', {}, format='json')
        self.assertEqual(response.status_code, 502)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'pending')

    @patch.object(StripePaymentStrategy, 'initiate')
    def test_paid_order_cannot_start_another_payment(self, initiate):
        order = self.order()
        order.status = 'paid'
        order.save()
        response = self.client.post('/api/payments/initiate/', {'order_id': order.pk, 'provider': 'stripe'})
        self.assertEqual(response.status_code, 400)
        initiate.assert_not_called()

    @patch.object(BkashPaymentStrategy, 'query', return_value={'status': 'pending'})
    def test_untrusted_cancel_callback_does_not_cancel_order(self, query):
        payment = self.payment('bkash')
        self.client.get(f'/api/payments/webhooks/bkash/?paymentID={payment.transaction_id}&status=cancel')
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'pending')
        query.assert_called_once()

    def test_order_detail_includes_payment_history(self):
        payment = self.payment()
        response = self.client.get(f'/api/orders/{payment.order_id}/')
        self.assertEqual(response.data['payments'][0]['id'], payment.pk)

    def test_invalid_category_filter_is_client_error(self):
        response = self.client.get('/api/products/?category=abc')
        self.assertEqual(response.status_code, 400)

    def test_admin_can_clear_product_category(self):
        self.user.is_staff = True
        self.user.save()
        self.product.category = Category.objects.create(name='Original')
        self.product.save()
        response = self.client.patch(f'/api/products/{self.product.pk}/', {'category': None}, format='json')
        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertIsNone(self.product.category)

    def test_ordered_product_delete_returns_conflict(self):
        self.order()
        self.user.is_staff = True
        self.user.save()
        response = self.client.delete(f'/api/products/{self.product.pk}/')
        self.assertEqual(response.status_code, 409)

    def test_category_cycle_rejected(self):
        self.user.is_staff = True
        self.user.save()
        parent = Category.objects.create(name='Parent')
        child = Category.objects.create(name='Child', parent=parent)
        response = self.client.patch(f'/api/products/categories/{parent.pk}/', {'parent': child.pk}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_duplicate_category_name_does_not_crash(self):
        self.user.is_staff = True
        self.user.save()
        Category.objects.create(name='Duplicate')
        response = self.client.post('/api/products/categories/', {'name': 'Duplicate'})
        self.assertIn(response.status_code, (201, 400))

    def test_profile_email_uniqueness_is_case_insensitive(self):
        User.objects.create_user(username='other', email='other@example.com')
        response = self.client.patch('/api/auth/profile/', {'email': 'OTHER@example.com'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_service_rejects_weak_password(self):
        with self.assertRaises(ValidationError):
            UserService.register(username='weak', email='weak@example.com', password='123')

    @override_settings(BKASH_APP_KEY='key', BKASH_APP_SECRET='secret', BKASH_USERNAME='user', BKASH_PASSWORD='pw')
    @patch('payments.strategies.requests.post', side_effect=requests.Timeout('timed out'))
    def test_bkash_token_timeout_is_normalized(self, _):
        with self.assertRaises(PaymentProviderError):
            BkashPaymentStrategy()._grant_token()

    @patch.object(StripePaymentStrategy, 'initiate', return_value={'transaction_id': 'reserved', 'raw_response': {'client_secret': 'test_secret'}})
    def test_repeated_initiation_reuses_payment_and_reservation(self, initiate):
        order = self.order()
        first, _ = PaymentService.initiate_payment(order, 'stripe')
        second, result = PaymentService.initiate_payment(order, 'stripe')
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(result['client_secret'], 'test_secret')
        self.assertEqual(initiate.call_count, 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        PaymentService._apply_result(first, {'status': 'success'})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    @patch.object(StripePaymentStrategy, 'initiate', return_value={'transaction_id': 'reserved', 'raw_response': {}})
    def test_failed_reserved_payment_releases_stock_once(self, _):
        payment, _ = PaymentService.initiate_payment(self.order(), 'stripe')
        PaymentService._apply_result(payment, {'status': 'failed'})
        PaymentService._apply_result(payment, {'status': 'failed'})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    @patch.object(StripePaymentStrategy, 'initiate', side_effect=PaymentProviderError('offline'))
    def test_initiation_failure_rolls_back_reservation(self, _):
        order = self.order()
        with self.assertRaises(PaymentProviderError):
            PaymentService.initiate_payment(order, 'stripe')
        self.product.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        self.assertFalse(order.stock_reserved)
        self.assertEqual(Payment.objects.count(), 0)

    @patch.object(StripePaymentStrategy, 'initiate', return_value={'transaction_id': 'reserved', 'raw_response': {}})
    def test_competing_order_cannot_charge_reserved_stock(self, initiate):
        self.product.stock = 2
        self.product.save()
        PaymentService.initiate_payment(self.order(), 'stripe')
        with self.assertRaises(ValidationError):
            PaymentService.initiate_payment(self.order(), 'stripe')
        self.assertEqual(initiate.call_count, 1)

    def test_legacy_shortage_rolls_back_all_stock_and_flags_review(self):
        payment = self.payment()
        other = Product.objects.create(name='Empty', sku='EMPTY', price='1.00', stock=0)
        OrderItem.objects.create(order=payment.order, product=other, quantity=1, price='1.00', subtotal='1.00')
        PaymentService._apply_result(payment, {'status': 'success'})
        payment.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertTrue(payment.order.needs_review)
        self.assertEqual(payment.order.status, 'paid')
        self.assertEqual(self.product.stock, 5)

    @patch.object(BkashPaymentStrategy, '_grant_token')
    def test_bkash_rejects_usd_without_contacting_provider(self, grant):
        with self.assertRaises(PaymentProviderError):
            BkashPaymentStrategy().initiate(self.order())
        grant.assert_not_called()

    def test_other_user_cannot_access_order_or_payment(self):
        payment = self.payment()
        other = User.objects.create_user(username='outsider', email='outsider@example.com')
        self.client.force_authenticate(other)
        for url in (f'/api/orders/{payment.order_id}/', f'/api/payments/{payment.pk}/'):
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(f'/api/payments/{payment.pk}/confirm/', {}).status_code, 404)

    def test_customer_cannot_modify_catalog_or_gain_staff_role(self):
        self.assertEqual(self.client.patch(f'/api/products/{self.product.pk}/', {'price': '0.01'}).status_code, 403)
        self.client.patch('/api/auth/profile/', {'is_staff': True}, format='json')
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)

    def test_amount_overflow_rejected_without_partial_order(self):
        self.product.price = Decimal('9999999999.99')
        self.product.save()
        response = self.client.post('/api/orders/', {'items': [{'product_id': self.product.pk, 'quantity': 2}]}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    @override_settings(STRIPE_WEBHOOK_SECRET='whsec_test')
    def test_real_invalid_stripe_signature_is_rejected(self):
        response = self.client.post('/api/payments/webhooks/stripe/', {'type': 'payment_intent.succeeded'}, format='json', HTTP_STRIPE_SIGNATURE='t=1,v1=invalid')
        self.assertEqual(response.status_code, 400)

    @patch.object(BkashPaymentStrategy, 'confirm', return_value={'status': 'success'})
    def test_fetch_default_accept_returns_json_not_redirect(self, _):
        payment = self.payment('bkash')
        response = self.client.get(f'/api/payments/webhooks/bkash/?paymentID={payment.transaction_id}&status=success', HTTP_ACCEPT='*/*')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'success')

    @patch.object(StripePaymentStrategy, 'confirm', return_value={'status': 'pending'})
    def test_stripe_query_supported(self, _):
        payment = self.payment()
        self.assertEqual(self.client.get(f'/api/payments/{payment.pk}/query/').status_code, 200)

    def test_password_whitespace_survives_registration_and_login(self):
        payload = {'username': 'spaces', 'email': 'spaces@example.test', 'password': '  Complex!4729-Space  '}
        self.assertEqual(self.client.post('/api/auth/register/', payload, format='json').status_code, 201)
        self.assertEqual(self.client.post('/api/auth/login/', {'username': 'spaces', 'password': payload['password']}, format='json').status_code, 200)

    def test_late_pending_result_cannot_reopen_failed_payment(self):
        payment = self.payment()
        PaymentService._apply_result(payment, {'status': 'failed'})
        PaymentService._apply_result(payment, {'status': 'pending'})
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'failed')

    @override_settings(STRIPE_SECRET_KEY='sk_test_qa', STRIPE_PUBLISHABLE_KEY='pk_test_qa')
    @patch('payments.strategies.stripe.PaymentIntent.create')
    def test_stripe_uses_order_currency_and_idempotency_key(self, create):
        from types import SimpleNamespace
        create.return_value = SimpleNamespace(id='pi_qa', client_secret='test', to_dict=lambda: {})
        order = self.order()
        order.currency = 'BDT'
        StripePaymentStrategy().initiate(order)
        self.assertEqual(create.call_args.kwargs['amount'], 2500)
        self.assertEqual(create.call_args.kwargs['currency'], 'bdt')
        self.assertEqual(create.call_args.kwargs['idempotency_key'], f'order-{order.pk}-stripe')

    @patch.object(BkashPaymentStrategy, '_grant_token', return_value='test')
    @patch.object(BkashPaymentStrategy, 'query', return_value={'status': 'success'})
    @patch('payments.strategies.requests.post', side_effect=requests.Timeout('lost execute response'))
    def test_bkash_execute_timeout_queries_outcome(self, post, query, grant):
        self.assertEqual(BkashPaymentStrategy().confirm('test')['status'], 'success')
        query.assert_called_once_with('test')

    def test_session_cart_deleted_product_cannot_create_empty_order(self):
        from orders.tests import FakeSession
        from orders.services import Cart, OrderService
        cart = Cart(FakeSession())
        cart.add(999999)
        with self.assertRaises(ValidationError):
            OrderService.create_order_from_cart(self.user, cart)
        self.assertEqual(Order.objects.count(), 0)

    def test_malformed_bkash_callback_is_client_error(self):
        response = self.client.post('/api/payments/webhooks/bkash/', ['invalid'], format='json')
        self.assertEqual(response.status_code, 400)
