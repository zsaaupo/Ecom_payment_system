from rest_framework import serializers

from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "parent"]
        read_only_fields = ["slug"]


class CategoryTreeNodeSerializer(serializers.Serializer):
    """Read-only serializer for the DFS-built, cached category tree."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    children = serializers.SerializerMethodField()

    def get_children(self, obj):
        return CategoryTreeNodeSerializer(obj["children"], many=True).data


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "name", "slug", "sku", "description", "price", "stock",
            "status", "category", "category_name", "image", "is_available",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        return value

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError("Stock cannot be negative.")
        return value
