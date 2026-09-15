from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from products.models import Product

from .models import Order, OrderItem
from .serializers import CreateOrderSerializer, OrderSerializer


class OrderViewSet(viewsets.ModelViewSet):
    """
    Requirement (2.1.1): "Users can view their own orders and payments."

    /api/orders/          GET (list own orders), POST (create order from `items`)
    /api/orders/{id}/     GET (own order detail)
    """
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items__product", "payments")

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = Order.objects.create(user=request.user, total_amount=Decimal("0.00"))
        total = Decimal("0.00")
        try:
            for line in serializer.validated_data["items"]:
                product = Product.objects.select_for_update().get(pk=line["product_id"])
                if not product.is_available:
                    raise DjangoValidationError(f"'{product.name}' is not available.")
                if product.stock < line["quantity"]:
                    raise DjangoValidationError(f"Insufficient stock for '{product.name}'.")
                subtotal = product.price * line["quantity"]
                OrderItem.objects.create(
                    order=order, product=product, quantity=line["quantity"],
                    price=product.price, subtotal=subtotal,
                )
                total += subtotal
                if total > Decimal('9999999999.99'):
                    raise DjangoValidationError('Order total exceeds the supported maximum.')
        except Product.DoesNotExist:
            raise ValidationError({"detail": "One or more products do not exist."})
        except DjangoValidationError as exc:
            raise ValidationError({"detail": exc.messages})

        order.total_amount = total
        order.save(update_fields=["total_amount"])
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)
