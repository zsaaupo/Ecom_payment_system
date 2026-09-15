"""
Service layer for Products & Categories.

Provides ProductService for catalog CRUD and concurrency-safe stock management,
and CategoryService for DFS category tree construction, caching, and branch-scoped
product recommendations.
"""
import logging

from django.core.cache import cache
from django.conf import settings
from django.db import transaction
from django.core.exceptions import ValidationError

from .models import Category, Product

logger = logging.getLogger("products")


class InsufficientStockError(Exception):
    """Raised when an order tries to reduce more stock than is available."""


class ProductService:
    """Business logic for creating/updating products and managing stock."""

    @staticmethod
    def create_product(*, name, sku, price, stock=0, description="", status=Product.Status.ACTIVE,
                        category=None, image=None):
        if price is None or price < 0:
            raise ValidationError({"price": "Price must be a non-negative number."})
        if stock is not None and stock < 0:
            raise ValidationError({"stock": "Stock cannot be negative."})

        product = Product(
            name=name, sku=sku, price=price, stock=stock, description=description,
            status=status, category=category,
        )
        if image:
            product.image = image
        product.full_clean()
        product.save()
        CategoryService.invalidate_tree_cache()
        logger.info("Product created: %s (sku=%s)", product.name, product.sku)
        return product

    @staticmethod
    def update_product(product: Product, **fields):
        for key, value in fields.items():
            if hasattr(product, key):
                setattr(product, key, value)
        product.full_clean()
        product.save()
        CategoryService.invalidate_tree_cache()
        logger.info("Product updated: %s (sku=%s)", product.name, product.sku)
        return product

    @staticmethod
    def delete_product(product: Product):
        sku = product.sku
        product.delete()
        CategoryService.invalidate_tree_cache()
        logger.info("Product deleted: sku=%s", sku)

    @staticmethod
    @transaction.atomic
    def reduce_stock(product_id: int, quantity: int):
        """
        Deterministic, concurrency-safe stock reduction.

        Uses SELECT ... FOR UPDATE (via select_for_update) inside an atomic
        transaction so two simultaneous payment confirmations for the same
        product can never oversell stock - the second transaction blocks
        until the first commits, then re-reads the up-to-date stock value.
        """
        if quantity <= 0:
            raise ValidationError("Quantity to reduce must be positive.")

        product = Product.objects.select_for_update().get(pk=product_id)
        if product.stock < quantity:
            raise InsufficientStockError(
                f"Cannot reduce stock of '{product.name}' by {quantity}: only {product.stock} left."
            )
        product.stock -= quantity
        if product.stock == 0:
            product.status = Product.Status.INACTIVE
        product.save(update_fields=["stock", "status", "updated_at"])
        logger.info("Stock reduced for %s: -%s (remaining=%s)", product.sku, quantity, product.stock)
        return product


class CategoryService:
    """
    Category tree construction (DFS) with caching, and DFS-based
    related-product recommendations.
    """

    @staticmethod
    def invalidate_tree_cache():
        cache.delete(settings.CATEGORY_TREE_CACHE_KEY)

    @staticmethod
    def _build_tree_dfs():
        """
        Depth-first traversal that builds a nested dict representation of
        the whole category tree in a single pass:

            {category_id: {"category": Category, "children": [...]}}

        DFS is implemented iteratively with an explicit stack (avoids
        Python recursion-limit issues on very deep trees) and visits each
        node exactly once, giving O(N) time for N categories.
        """
        categories = list(Category.objects.select_related("parent").all())
        by_parent = {}
        by_id = {}
        for cat in categories:
            by_id[cat.id] = cat
            by_parent.setdefault(cat.parent_id, []).append(cat)

        def build_node(category):
            return {
                "id": category.id,
                "name": category.name,
                "slug": category.slug,
                "children": [],
            }

        nodes_by_id = {}
        roots = []

        # Iterative DFS using an explicit stack of (category, parent_node_or_None)
        stack = [(root, None) for root in by_parent.get(None, [])]
        while stack:
            category, parent_node = stack.pop()  # LIFO -> depth-first
            node = build_node(category)
            nodes_by_id[category.id] = node
            if parent_node is None:
                roots.append(node)
            else:
                parent_node["children"].append(node)
            # push children so they are visited before siblings already on the stack
            for child in reversed(by_parent.get(category.id, [])):
                stack.append((child, node))

        return {"roots": roots, "nodes_by_id": nodes_by_id}

    @classmethod
    def get_category_tree(cls, force_refresh=False):
        """
        Returns the cached category tree, building and caching it on a
        cache miss to minimize database queries.
        """
        key = settings.CATEGORY_TREE_CACHE_KEY
        tree = None if force_refresh else cache.get(key)
        if tree is None:
            logger.debug("Category tree cache miss - rebuilding via DFS")
            tree = cls._build_tree_dfs()
            cache.set(key, tree, settings.CATEGORY_TREE_CACHE_TTL)
        else:
            logger.debug("Category tree cache hit")
        return tree

    @classmethod
    def get_descendant_ids_dfs(cls, category_id):
        """
        Depth-first traversal from a given category down to all of its
        descendants, using the cached tree (no DB hit on cache hit).
        Used to scope "related products" to a whole category branch.
        """
        tree = cls.get_category_tree()
        node = tree["nodes_by_id"].get(category_id)
        if not node:
            return [category_id]

        ids = []
        stack = [node]
        while stack:
            current = stack.pop()
            ids.append(current["id"])
            stack.extend(current["children"])
        return ids

    @classmethod
    def get_related_products(cls, product: Product, limit=8):
        """
        Product recommendation: DFS the category subtree that `product`
        belongs to, then return other active, in-stock products anywhere
        in that branch.
        """
        if not product.category_id:
            return Product.objects.filter(status=Product.Status.ACTIVE, stock__gt=0).exclude(pk=product.pk)[:limit]

        category_ids = cls.get_descendant_ids_dfs(product.category_id)
        return (
            Product.objects.filter(category_id__in=category_ids, status=Product.Status.ACTIVE, stock__gt=0)
            .exclude(pk=product.pk)
            .order_by("-created_at")[:limit]
        )
