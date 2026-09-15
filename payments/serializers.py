from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    currency = serializers.CharField(source='order.currency', read_only=True)
    class Meta:
        model = Payment
        fields = ["id", "order", "provider", "transaction_id", "status", "amount", "currency", "created_at", "updated_at"]
        read_only_fields = fields


class InitiatePaymentSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    provider = serializers.ChoiceField(choices=["stripe", "bkash"])


class ConfirmPaymentSerializer(serializers.Serializer):
    transaction_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
