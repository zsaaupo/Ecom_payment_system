from django.conf import settings
from django.db import models


def default_currency():
    return settings.STORE_CURRENCY


class Order(models.Model):
    """
    Requirement (2.1.3 Order Management):
    id, user_id (FK), total_amount, status (pending, paid, canceled), timestamps.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        CANCELED = "canceled", "Canceled"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="orders", on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default=default_currency)
    stock_reserved = models.BooleanField(default=False)
    needs_review = models.BooleanField(default=False, help_text='Payment succeeded but fulfillment needs manual review.')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["status"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.pk} ({self.status})"


class OrderItem(models.Model):
    """
    Requirement (2.1.3): OrderItems table -
    id, order_id (FK), product_id (FK), quantity, price, subtotal.
    """
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey("products.Product", related_name="order_items", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=12, decimal_places=2, help_text="Unit price at time of order")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["product"]),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.product.name} (Order #{self.order_id})"
