"""
Service layer for the Orders domain.

Provides OrderService for creating and managing order status transitions,
and the Cart class for session-backed shopping cart encapsulation.
Line subtotals and order totals are calculated using exact Decimal arithmetic.
"""
import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from products.models import Product

from .models import Order, OrderItem

logger = logging.getLogger("orders")

CART_SESSION_KEY = "cart"


class Cart:
    """
    Thin OOP wrapper around the Django session used to represent the
    logged-in (or anonymous, pre-checkout) user's shopping cart as
    {product_id: quantity}.
    """

    def __init__(self, session):
        self.session = session
        self.session.setdefault(CART_SESSION_KEY, {})

    @property
    def _data(self):
        return self.session[CART_SESSION_KEY]

    def add(self, product_id: int, quantity: int = 1):
        product_id = str(product_id)
        self._data[product_id] = self._data.get(product_id, 0) + max(1, quantity)
        self._save()

    def set_quantity(self, product_id: int, quantity: int):
        product_id = str(product_id)
        if quantity <= 0:
            self._data.pop(product_id, None)
        else:
            self._data[product_id] = quantity
        self._save()

    def remove(self, product_id: int):
        self._data.pop(str(product_id), None)
        self._save()

    def clear(self):
        self.session[CART_SESSION_KEY] = {}
        self._save()

    def _save(self):
        self.session.modified = True

    def items(self):
        """Yields (Product, quantity) pairs, skipping products that vanished."""
        if not self._data:
            return
        products = Product.objects.filter(pk__in=[int(pid) for pid in self._data.keys()])
        products_by_id = {p.pk: p for p in products}
        for pid, qty in self._data.items():
            product = products_by_id.get(int(pid))
            if product:
                yield product, qty

    def total_items(self):
        return sum(self._data.values())

    def total_price(self) -> Decimal:
        return sum((product.price * qty for product, qty in self.items()), Decimal("0.00"))

    def is_empty(self):
        return len(self._data) == 0


class OrderService:
    """Business logic for creating and transitioning orders."""

    @staticmethod
    @transaction.atomic
    def create_order_from_cart(user, cart: Cart) -> Order:
        """
        Creates a Order + OrderItems from the given cart.

        Deterministic total/subtotal algorithm:
            subtotal_i = quantity_i * unit_price_i           (per line)
            total      = sum(subtotal_i for all lines)       (order total)
        Both are computed with Decimal (never float) so the same cart
        always yields exactly the same total, with no rounding drift.
        """
        if cart.is_empty():
            raise ValidationError("Cannot create an order from an empty cart.")
        lines = list(cart.items())
        if len(lines) != len(cart._data):
            raise ValidationError('One or more cart products no longer exist.')

        order = Order.objects.create(user=user, total_amount=Decimal("0.00"), status=Order.Status.PENDING)
        total = Decimal("0.00")

        for product, quantity in lines:
            if not isinstance(quantity, int) or quantity <= 0:
                raise ValidationError('Quantity must be a positive integer.')
            if not product.is_available:
                raise ValidationError(f"'{product.name}' is not currently available.")
            if product.stock < quantity:
                raise ValidationError(f"Only {product.stock} unit(s) of '{product.name}' are in stock.")

            unit_price = product.price
            subtotal = unit_price * quantity
            OrderItem.objects.create(
                order=order, product=product, quantity=quantity,
                price=unit_price, subtotal=subtotal,
            )
            total += subtotal
            if total > Decimal('9999999999.99'):
                raise ValidationError('Order total exceeds the supported maximum.')

        order.total_amount = total
        order.save(update_fields=["total_amount"])
        logger.info("Order #%s created for user %s: total=%s", order.pk, user.username, total)
        return order

    @staticmethod
    def mark_paid(order: Order):
        order.status = Order.Status.PAID
        order.save(update_fields=["status", "updated_at"])
        logger.info("Order #%s marked PAID", order.pk)

    @staticmethod
    def cancel(order: Order):
        order.status = Order.Status.CANCELED
        order.save(update_fields=["status", "updated_at"])
        logger.info("Order #%s CANCELED", order.pk)
