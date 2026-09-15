from rest_framework import serializers

from products.serializers import ProductSerializer
from payments.serializers import PaymentSerializer

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "quantity", "price", "subtotal"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ["id", "user", "status", "total_amount", "currency", "stock_reserved", "needs_review", "items", "payments", "created_at", "updated_at"]
        read_only_fields = ["id", "user", "status", "total_amount", "created_at", "updated_at"]


class CartItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, max_value=2147483647)


class CreateOrderSerializer(serializers.Serializer):
    """Payload for POST /api/orders/ when creating an order directly via API
    (as opposed to the session-cart-driven web checkout)."""
    items = CartItemInputSerializer(many=True, allow_empty=False, max_length=100)

    def validate_items(self, items):
        ids = [line['product_id'] for line in items]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError('Each product must appear only once.')
        return items
