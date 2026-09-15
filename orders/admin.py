from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "price", "subtotal")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "total_amount", "currency", "stock_reserved", "needs_review", "created_at")
    list_filter = ("status", "needs_review", "stock_reserved")
    search_fields = ("id", "user__username", "user__email")
    inlines = [OrderItemInline]
    readonly_fields = ("user", "status", "total_amount", "currency", "stock_reserved", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
