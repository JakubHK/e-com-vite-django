from django.contrib import admin
from .models import Category, Product, Order, OrderItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "slug")
    list_display = ("title", "slug", "created_at")
    ordering = ("title",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "slug", "description")
    list_filter = ("is_active", "category")
    list_display = (
        "title",
        "category",
        "price",
        "currency",
        "is_active",
        "created_at",
    )
    list_editable = ("is_active",)
    autocomplete_fields = ("category",)
    ordering = ("title",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ("product", "quantity", "unit_price", "currency")
    autocomplete_fields = ("product",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    readonly_fields = ("created_at", "updated_at", "total")
    list_display = ("id", "email", "status", "total", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("email", "name", "street", "city", "zip")
    fieldsets = (
        ("Status", {"fields": ("status",)}),
        ("Contact", {"fields": ("email", "phone")}),
        ("Shipping", {"fields": ("name", "street", "city", "zip", "country")}),
        ("Totals", {"fields": ("total",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
