from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from products.models import Product
from users.models import User

from .models import Order
from .services import Cart, OrderService


class FakeSession(dict):
    """Minimal stand-in for Django's session object (dict + .modified),
    so Cart can be unit-tested without spinning up a real request/session."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.modified = False


class OrderTotalAlgorithmTests(TestCase):
    """Requirement 2.2.3: deterministic total/subtotal calculation."""

    def setUp(self):
        self.user = User.objects.create_user(username="dana", email="dana@example.com", password="pass12345")
        self.p1 = Product.objects.create(name="A", sku="SKU-A", price=Decimal("9.99"), stock=10)
        self.p2 = Product.objects.create(name="B", sku="SKU-B", price=Decimal("4.50"), stock=10)

    def test_order_total_is_sum_of_subtotals(self):
        session = FakeSession()
        cart = Cart(session)
        cart.add(self.p1.id, 2)   # 19.98
        cart.add(self.p2.id, 3)   # 13.50
        order = OrderService.create_order_from_cart(self.user, cart)
        self.assertEqual(order.total_amount, Decimal("33.48"))
        self.assertEqual(order.items.count(), 2)
        for item in order.items.all():
            self.assertEqual(item.subtotal, item.price * item.quantity)

    def test_cannot_order_more_than_stock(self):
        session = FakeSession()
        cart = Cart(session)
        cart.add(self.p1.id, 999)
        with self.assertRaises(ValidationError):
            OrderService.create_order_from_cart(self.user, cart)

    def test_cannot_create_order_from_empty_cart(self):
        session = FakeSession()
        cart = Cart(session)
        with self.assertRaises(ValidationError):
            OrderService.create_order_from_cart(self.user, cart)


class OrderAPITests(TestCase):
    """API tests for authentication + order endpoints (deliverable 4.4)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="frank", email="frank@example.com", password="pass12345")
        self.token = Token.objects.create(user=self.user)
        self.product = Product.objects.create(name="Gadget", sku="SKU-G1", price=Decimal("25.00"), stock=10)

    def test_orders_require_authentication(self):
        response = self.client.get("/api/orders/")
        self.assertEqual(response.status_code, 401)

    def test_authenticated_user_can_create_and_list_own_orders(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.post("/api/orders/", {
            "items": [{"product_id": self.product.id, "quantity": 2}]
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(response.data["total_amount"]), Decimal("50.00"))

        list_response = self.client.get("/api/orders/")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data["results"]), 1)

    def test_user_cannot_see_others_orders(self):
        other = User.objects.create_user(username="grace", email="grace@example.com", password="pass12345")
        Order.objects.create(user=other, total_amount=Decimal("10.00"))

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.get("/api/orders/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 0)
