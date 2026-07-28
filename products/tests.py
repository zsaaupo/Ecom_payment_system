from decimal import Decimal

from django.test import TestCase

from .models import Category, Product
from .services import CategoryService, InsufficientStockError, ProductService


class ProductModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Books")

    def test_sku_must_be_unique(self):
        Product.objects.create(name="Book A", sku="SKU-1", price=Decimal("10.00"), stock=5, category=self.category)
        with self.assertRaises(Exception):
            Product.objects.create(name="Book B", sku="SKU-1", price=Decimal("12.00"), stock=3, category=self.category)

    def test_is_available_property(self):
        p = Product.objects.create(name="Book C", sku="SKU-2", price=Decimal("10.00"), stock=0, category=self.category)
        self.assertFalse(p.is_available)
        p.stock = 5
        p.save()
        self.assertTrue(p.is_available)


class StockReductionAlgorithmTests(TestCase):
    """Requirement 2.2.3: deterministic, safe stock reduction algorithm."""

    def setUp(self):
        self.product = Product.objects.create(name="Widget", sku="SKU-W1", price=Decimal("5.00"), stock=10)

    def test_reduce_stock_happy_path(self):
        ProductService.reduce_stock(self.product.id, 3)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 7)

    def test_reduce_stock_insufficient_raises(self):
        with self.assertRaises(InsufficientStockError):
            ProductService.reduce_stock(self.product.id, 999)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)  # unchanged, transaction rolled back

    def test_reduce_stock_to_zero_marks_inactive(self):
        ProductService.reduce_stock(self.product.id, 10)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)
        self.assertEqual(self.product.status, Product.Status.INACTIVE)


class CategoryDFSTests(TestCase):
    """Requirement 2.2.5: DFS traversal + caching of the category tree."""

    def setUp(self):
        self.electronics = Category.objects.create(name="Electronics")
        self.phones = Category.objects.create(name="Phones", parent=self.electronics)
        self.accessories = Category.objects.create(name="Accessories", parent=self.electronics)
        self.cases = Category.objects.create(name="Cases", parent=self.accessories)
        self.fashion = Category.objects.create(name="Fashion")

        # A product sitting directly in the root "Electronics" category, so
        # its DFS subtree covers Electronics + Phones + Accessories + Cases.
        self.hub = Product.objects.create(name="Smart Hub", sku="SKU-HUB", price=Decimal("120"), stock=10, category=self.electronics)
        self.phone = Product.objects.create(name="Phone X", sku="SKU-PX", price=Decimal("500"), stock=10, category=self.phones)
        self.case = Product.objects.create(name="Case Y", sku="SKU-CY", price=Decimal("15"), stock=10, category=self.cases)
        self.shirt = Product.objects.create(name="Shirt Z", sku="SKU-SZ", price=Decimal("20"), stock=10, category=self.fashion)

    def test_tree_has_expected_roots(self):
        tree = CategoryService.get_category_tree()
        root_names = {r["name"] for r in tree["roots"]}
        self.assertEqual(root_names, {"Electronics", "Fashion"})

    def test_descendant_ids_include_all_nested_children(self):
        ids = set(CategoryService.get_descendant_ids_dfs(self.electronics.id))
        expected = {self.electronics.id, self.phones.id, self.accessories.id, self.cases.id}
        self.assertEqual(ids, expected)

    def test_related_products_stay_within_branch(self):
        related = list(CategoryService.get_related_products(self.hub))
        related_ids = {p.id for p in related}
        # 'Phone X' and 'Case Y' are both nested under Electronics (the hub's
        # own category), so DFS from Electronics downward should surface both.
        self.assertIn(self.phone.id, related_ids)
        self.assertIn(self.case.id, related_ids)
        # 'Shirt Z' is under Fashion, a completely different branch.
        self.assertNotIn(self.shirt.id, related_ids)

    def test_tree_cache_invalidates_on_new_category(self):
        CategoryService.get_category_tree()  # warm the cache
        Category.objects.create(name="Toys")  # triggers post_save signal -> cache invalidation
        tree = CategoryService.get_category_tree()
        root_names = {r["name"] for r in tree["roots"]}
        self.assertIn("Toys", root_names)

    def test_product_list_category_filter_includes_subcategories(self):
        url = f"/api/products/?category={self.electronics.id}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        results = data["results"] if isinstance(data, dict) and "results" in data else data
        product_ids = {p["id"] for p in results}
        # Electronics contains Smart Hub (direct), Phone X (under Phones), Case Y (under Cases)
        self.assertIn(self.hub.id, product_ids)
        self.assertIn(self.phone.id, product_ids)
        self.assertIn(self.case.id, product_ids)
        # Shirt Z is under Fashion, should not be included
        self.assertNotIn(self.shirt.id, product_ids)
