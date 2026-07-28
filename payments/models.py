from django.db import models


class Payment(models.Model):
    """
    Requirement (2.1.5 Payment Table):
    id, order_id (FK), provider (stripe/bkash), transaction_id (unique),
    status, raw_response (JSON), timestamps.
    """

    class Provider(models.TextChoices):
        STRIPE = "stripe", "Stripe"
        BKASH = "bkash", "bKash"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    order = models.ForeignKey("orders.Order", related_name="payments", on_delete=models.CASCADE)
    provider = models.CharField(max_length=10, choices=Provider.choices)
    transaction_id = models.CharField(max_length=128, unique=True, db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    raw_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["provider"]),
            models.Index(fields=["status"]),
            models.Index(fields=["transaction_id"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.provider}:{self.transaction_id} ({self.status})"
