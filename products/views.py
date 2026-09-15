from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from django.db.models.deletion import ProtectedError

from .models import Category, Product
from .permissions import IsAdminOrReadOnly
from .serializers import CategorySerializer, CategoryTreeNodeSerializer, ProductSerializer
from .services import CategoryService, ProductService


class CategoryViewSet(viewsets.ModelViewSet):
    """
    /api/products/categories/            GET (list), POST (admin)
    /api/products/categories/{id}/       GET, PUT/PATCH, DELETE (admin)
    /api/products/categories/tree/       GET - full DFS-built, cached tree
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "pk"

    def perform_create(self, serializer):
        serializer.save()
        CategoryService.invalidate_tree_cache()

    def perform_update(self, serializer):
        serializer.save()
        CategoryService.invalidate_tree_cache()

    def perform_destroy(self, instance):
        instance.delete()
        CategoryService.invalidate_tree_cache()

    @action(detail=False, methods=["get"])
    def tree(self, request):
        tree = CategoryService.get_category_tree()
        return Response(CategoryTreeNodeSerializer(tree["roots"], many=True).data)


class ProductViewSet(viewsets.ModelViewSet):
    """
    /api/products/                GET (list, public), POST (admin)
    /api/products/{id}/           GET (public), PUT/PATCH, DELETE (admin)
    /api/products/{id}/related/   GET - DFS category-based recommendations
    """
    queryset = Product.objects.select_related("category").all()
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "pk"

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = self.request.query_params.get("status")
        category_id = self.request.query_params.get("category")
        search = self.request.query_params.get("q")
        if not (self.request.user and self.request.user.is_staff):
            qs = qs.filter(status=Product.Status.ACTIVE)
        elif status_param:
            qs = qs.filter(status=status_param)
        if category_id:
            try:
                cat_id_int = int(category_id)
                category_ids = CategoryService.get_descendant_ids_dfs(cat_id_int)
                qs = qs.filter(category_id__in=category_ids)
            except (ValueError, TypeError):
                raise ValidationError({'category': 'Enter a valid category ID.'})
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            product = ProductService.create_product(**serializer.validated_data)
        except DjangoValidationError as exc:
            return Response({"detail": exc.message_dict if hasattr(exc, "message_dict") else str(exc)},
                             status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(product).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        try:
            product = ProductService.update_product(instance, **serializer.validated_data)
        except DjangoValidationError as exc:
            return Response({"detail": exc.message_dict if hasattr(exc, "message_dict") else str(exc)},
                             status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(product).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            ProductService.delete_product(instance)
        except ProtectedError:
            return Response({'detail': 'This product belongs to an order. Set it inactive instead.'}, status=409)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def related(self, request, pk=None):
        product = self.get_object()
        related = CategoryService.get_related_products(product)
        return Response(self.get_serializer(related, many=True).data)


class CategoryTreeView(APIView):
    """GET /api/products/categories/tree/ (standalone, no auth needed)."""
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request):
        tree = CategoryService.get_category_tree()
        return Response(CategoryTreeNodeSerializer(tree["roots"], many=True).data)
