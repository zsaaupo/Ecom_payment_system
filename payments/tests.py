import json
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from orders.models import Order
from products.models import Product
from users.models import User

from .models import Payment
from .services import PaymentService
from .strategies import (
    BkashPaymentStrategy,
    PaymentContext,
    PaymentProviderError,
    STRATEGY_REGISTRY,
    StripePaymentStrategy,
)


class StrategyRegistryTests(TestCase):
    """Requirement 2.2.4: Strategy pattern - providers are pluggable via a registry."""

    def test_registry_contains_stripe_and_bkash(self):
        self.assertIn("stripe", STRATEGY_REGISTRY)
        self.assertIn("bkash", STRATEGY_REGISTRY)
        self.assertIs(STRATEGY_REGISTRY["stripe"], StripePaymentStrategy)
        self.assertIs(STRATEGY_REGISTRY["bkash"], BkashPaymentStrategy)

    def test_unknown_provider_raises(self):
        with self.assertRaises(PaymentProviderError):
            PaymentContext("unknown_provider")

    def test_context_delegates_to_correct_strategy_class(self):
        self.assertIsInstance(PaymentContext("stripe").strategy, StripePaymentStrategy)
        self.assertIsInstance(PaymentContext("bkash").strategy, BkashPaymentStrategy)


class PaymentServiceOrderFlowTests(TestCase):
    """
    Requirement 2.1.6 Order Flow, steps 3-6: initiate -> provider confirms ->
    order status updates -> stock is reduced. Provider network calls are
    mocked so these tests are fast and hermetic.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="henry", email="henry@example.com", password="pass12345")
        self.product = Product.objects.create(name="Lamp", sku="SKU-LAMP", price=Decimal("40.00"), stock=5)
        self.order = Order.objects.create(user=self.user, total_amount=Decimal("80.00"))
        from orders.models import OrderItem
        OrderItem.objects.create(order=self.order, product=self.product, quantity=2,
                                  price=Decimal("40.00"), subtotal=Decimal("80.00"))

    @patch.object(StripePaymentStrategy, "initiate")
    def test_initiate_payment_creates_payment_record(self, mock_initiate):
        mock_initiate.return_value = {
            "transaction_id": "pi_test_123", "status": "pending",
            "client_secret": "secret", "raw_response": {"id": "pi_test_123"},
        }
        payment, result = PaymentService.initiate_payment(self.order, "stripe")
        self.assertEqual(payment.provider, "stripe")
        self.assertEqual(payment.transaction_id, "pi_test_123")
        self.assertEqual(payment.status, Payment.Status.PENDING)

    @patch.object(StripePaymentStrategy, "confirm")
    @patch.object(StripePaymentStrategy, "initiate")
    def test_successful_confirmation_marks_order_paid_and_reduces_stock(self, mock_initiate, mock_confirm):
        mock_initiate.return_value = {"transaction_id": "pi_test_456", "status": "pending", "raw_response": {}}
        mock_confirm.return_value = {"status": "success", "raw_response": {"id": "pi_test_456"}}

        payment, _ = PaymentService.initiate_payment(self.order, "stripe")
        PaymentService.confirm_payment(payment)

        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertEqual(self.product.stock, 3)  # 5 - 2

    @patch.object(StripePaymentStrategy, "confirm")
    @patch.object(StripePaymentStrategy, "initiate")
    def test_failed_confirmation_cancels_order_and_keeps_stock(self, mock_initiate, mock_confirm):
        mock_initiate.return_value = {"transaction_id": "pi_test_789", "status": "pending", "raw_response": {}}
        mock_confirm.return_value = {"status": "failed", "raw_response": {"id": "pi_test_789"}}

        payment, _ = PaymentService.initiate_payment(self.order, "stripe")
        PaymentService.confirm_payment(payment)

        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELED)
        self.assertEqual(self.product.stock, 5)  # unchanged


class StripeWebhookTests(TestCase):
    """Requirement 2.1.4: 'Webhook for payment updates.' (Stripe)."""

    def setUp(self):
        self.user = User.objects.create_user(username="ivy", email="ivy@example.com", password="pass12345")
        self.product = Product.objects.create(name="Mug", sku="SKU-MUG", price=Decimal("15.00"), stock=10)
        self.order = Order.objects.create(user=self.user, total_amount=Decimal("15.00"))
        from orders.models import OrderItem
        OrderItem.objects.create(order=self.order, product=self.product, quantity=1,
                                  price=Decimal("15.00"), subtotal=Decimal("15.00"))
        self.payment = Payment.objects.create(
            order=self.order, provider=Payment.Provider.STRIPE, transaction_id="pi_webhook_1",
            status=Payment.Status.PENDING, amount=Decimal("15.00"),
        )

    def test_webhook_rejects_invalid_signature(self):
        client = APIClient()
        response = client.post(
            "/api/payments/webhooks/stripe/",
            data=json.dumps({"type": "payment_intent.succeeded"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="invalid_signature",
        )
        self.assertEqual(response.status_code, 400)

    @patch("payments.strategies.StripePaymentStrategy.verify_webhook")
    def test_webhook_succeeded_event_marks_order_paid(self, mock_verify):
        mock_verify.return_value = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_webhook_1"}},
        }
        client = APIClient()
        response = client.post(
            "/api/payments/webhooks/stripe/",
            data=json.dumps({"type": "payment_intent.succeeded"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)

    @patch("payments.strategies.StripePaymentStrategy.verify_webhook")
    def test_webhook_declined_attempt_keeps_order_retryable(self, mock_verify):
        mock_verify.return_value = {
            "type": "payment_intent.payment_failed",
            "data": {"object": {"id": "pi_webhook_1"}},
        }
        client = APIClient()
        response = client.post(
            "/api/payments/webhooks/stripe/",
            data=json.dumps({"type": "payment_intent.payment_failed"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)


class BkashCallbackTests(TestCase):
    """Requirement 2.1.4 (bKash): callback / execute / query flow."""

    def setUp(self):
        self.user = User.objects.create_user(username="jack", email="jack@example.com", password="pass12345")
        self.product = Product.objects.create(name="Bag", sku="SKU-BAG", price=Decimal("30.00"), stock=10)
        self.order = Order.objects.create(user=self.user, total_amount=Decimal("30.00"))
        from orders.models import OrderItem
        OrderItem.objects.create(order=self.order, product=self.product, quantity=1,
                                  price=Decimal("30.00"), subtotal=Decimal("30.00"))
        self.payment = Payment.objects.create(
            order=self.order, provider=Payment.Provider.BKASH, transaction_id="bkash_pay_1",
            status=Payment.Status.PENDING, amount=Decimal("30.00"),
        )

    def test_callback_missing_payment_id_returns_400(self):
        client = APIClient()
        response = client.get("/api/payments/webhooks/bkash/")
        self.assertEqual(response.status_code, 400)

    @patch.object(BkashPaymentStrategy, 'query', return_value={'status': 'failed'})
    def test_callback_verified_cancel_marks_payment_failed(self, mock_query):
        client = APIClient()
        response = client.get("/api/payments/webhooks/bkash/?paymentID=bkash_pay_1&status=cancel")
        self.assertEqual(response.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.FAILED)

    @patch.object(BkashPaymentStrategy, "confirm")
    def test_callback_success_executes_payment_and_marks_order_paid(self, mock_confirm):
        mock_confirm.return_value = {"status": "success", "raw_response": {"transactionStatus": "Completed"}}
        client = APIClient()
        response = client.get("/api/payments/webhooks/bkash/?paymentID=bkash_pay_1&status=success")
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
