"""
Deliverable (4.2 Code Deliverables): "Seeders for admin user and sample
products."

Usage:
    python manage.py seed_data
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from products.models import Category, Product
from products.services import CategoryService

User = get_user_model()

CATEGORY_TREE = {
    "Electronics": {
        "Mobile Phones": {},
        "Laptops": {},
        "Audio": {
            "Headphones": {},
            "Speakers": {},
        },
    },
    "Fashion": {
        "Men": {},
        "Women": {},
    },
    "Home & Living": {
        "Kitchen": {},
        "Furniture": {},
    },
}

SAMPLE_PRODUCTS = [
    ("iPhone 15", "Mobile Phones", "SKU-IPH15", Decimal("999.00"), 25,
     "Apple's flagship smartphone with A16 chip and a 48MP main camera."),
    ("Samsung Galaxy S24", "Mobile Phones", "SKU-SGS24", Decimal("899.00"), 30,
     "Samsung's flagship Android phone with a dynamic AMOLED display."),
    ("MacBook Air M3", "Laptops", "SKU-MBA-M3", Decimal("1299.00"), 15,
     "13-inch ultralight laptop with the Apple M3 chip and all-day battery."),
    ("Dell XPS 14", "Laptops", "SKU-DXPS14", Decimal("1499.00"), 12,
     "Premium Windows ultrabook with an InfinityEdge display."),
    ("Sony WH-1000XM5", "Headphones", "SKU-SONY-XM5", Decimal("349.00"), 40,
     "Industry-leading noise-cancelling over-ear headphones."),
    ("Bose QuietComfort Earbuds", "Headphones", "SKU-BOSE-QCE", Decimal("249.00"), 35,
     "Compact noise-cancelling earbuds with a comfortable fit."),
    ("JBL Flip 6", "Speakers", "SKU-JBL-FLIP6", Decimal("129.00"), 50,
     "Portable waterproof Bluetooth speaker with punchy bass."),
    ("Men's Oxford Shirt", "Men", "SKU-MEN-OXF01", Decimal("39.00"), 100,
     "Classic tailored-fit cotton oxford shirt."),
    ("Men's Denim Jacket", "Men", "SKU-MEN-DEN02", Decimal("79.00"), 60,
     "Mid-weight denim jacket with a relaxed fit."),
    ("Women's Wrap Dress", "Women", "SKU-WOM-WRP01", Decimal("59.00"), 80,
     "Elegant wrap dress in breathable viscose."),
    ("Women's Tailored Blazer", "Women", "SKU-WOM-BLZ02", Decimal("99.00"), 45,
     "Structured blazer that pairs with both formal and casual outfits."),
    ("Ceramic Cookware Set", "Kitchen", "SKU-KIT-CER01", Decimal("149.00"), 20,
     "10-piece non-stick ceramic-coated cookware set."),
    ("Stainless Steel Knife Set", "Kitchen", "SKU-KIT-KNF02", Decimal("89.00"), 30,
     "5-piece forged stainless steel kitchen knife set."),
    ("Oak Dining Table", "Furniture", "SKU-FUR-TBL01", Decimal("599.00"), 8,
     "Solid oak dining table, seats six."),
    ("Ergonomic Office Chair", "Furniture", "SKU-FUR-CHR02", Decimal("219.00"), 18,
     "Adjustable ergonomic mesh-back office chair."),
]


class Command(BaseCommand):
    help = "Seeds an admin user, a category hierarchy, and sample products."

    def add_arguments(self, parser):
        parser.add_argument("--admin-username", default="admin")
        parser.add_argument("--admin-email", default="admin@example.com")
        parser.add_argument("--admin-password", default=None, help='Optional initial admin password; otherwise use createsuperuser separately.')

    @transaction.atomic
    def handle(self, *args, **options):
        if options['admin_password']:
            admin_user, created = User.objects.get_or_create(
                username=options['admin_username'],
                defaults={'email': options['admin_email'], 'is_staff': True, 'is_superuser': True},
            )
            if created:
                from django.contrib.auth.password_validation import validate_password
                validate_password(options['admin_password'], user=admin_user)
                admin_user.set_password(options['admin_password'])
                admin_user.save()
                self.stdout.write(self.style.SUCCESS(f"Created admin '{admin_user.username}'."))
        else:
            self.stdout.write('No admin password supplied; seeding catalog only.')

        self.stdout.write("Seeding category tree...")
        name_to_category = {}

        def create_categories(tree, parent=None):
            for name, subtree in tree.items():
                category, _ = Category.objects.get_or_create(name=name, parent=parent)
                name_to_category[name] = category
                create_categories(subtree, parent=category)

        create_categories(CATEGORY_TREE)
        self.stdout.write(self.style.SUCCESS(f"  {Category.objects.count()} categories present."))

        self.stdout.write("Seeding sample products...")
        created_count = 0
        for name, category_name, sku, price, stock, description in SAMPLE_PRODUCTS:
            _, was_created = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "category": name_to_category[category_name],
                    "price": price,
                    "stock": stock,
                    "description": description,
                    "status": Product.Status.ACTIVE,
                },
            )
            created_count += int(was_created)
        self.stdout.write(self.style.SUCCESS(
            f"  {created_count} new products created ({Product.objects.count()} total)."
        ))

        CategoryService.invalidate_tree_cache()
        self.stdout.write(self.style.SUCCESS("Seeding complete."))
