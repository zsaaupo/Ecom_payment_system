from django.contrib import admin

from .models import Category, Product
from .services import CategoryService


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "slug")
    list_filter = ("parent",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        CategoryService.invalidate_tree_cache()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        CategoryService.invalidate_tree_cache()


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "category", "price", "stock", "status", "created_at")
    list_filter = ("status", "category")
    search_fields = ("name", "sku", "description")
    prepopulated_fields = {}
    readonly_fields = ("created_at", "updated_at")
    list_editable = ("price", "stock", "status")
