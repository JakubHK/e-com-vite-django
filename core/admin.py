from django.contrib import admin
from django.db.models import Count
from django.http import HttpResponse
from django.utils.html import format_html
from django.template.response import TemplateResponse
from django.contrib import messages
from django import forms
from django.conf import settings
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
import csv
import uuid

from .models import Category, Product, Order, OrderItem, OrderStatus, OrderTransitionLog
from .workflow.service import TransitionService


# Admin site branding
admin.site.site_header = "E‑Com Admin"
admin.site.site_title = "E‑Com Admin"
admin.site.index_title = "Administration"


class ApplyTransitionForm(forms.Form):
    target_state = forms.ChoiceField(choices=())
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    dry_run = forms.BooleanField(required=False, initial=False, help_text="Validate only; do not persist changes")

    def __init__(self, *args, **kwargs):
        choices = kwargs.pop("choices", [])
        super().__init__(*args, **kwargs)
        self.fields["target_state"].choices = choices


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "slug")
    ordering = ("title",)
    readonly_fields = ("created_at", "updated_at")
    list_display = ("title", "slug", "products_count", "created_at")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(products_count=Count("products"))

    @admin.display(ordering="products_count", description="Products")
    def products_count(self, obj):
        return getattr(obj, "products_count", 0)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "slug", "description")
    list_filter = ("is_active", "category")
    list_select_related = ("category",)
    date_hierarchy = "created_at"
    list_per_page = 50
    ordering = ("title",)
    autocomplete_fields = ("category",)
    readonly_fields = ("created_at", "updated_at", "thumbnail")

    list_display = (
        "thumbnail",
        "title",
        "category",
        "price",
        "currency",
        "is_active",
        "created_at",
    )
    list_editable = ("is_active",)

    fieldsets = (
        ("Basics", {"fields": ("category", "title", "slug", "description", "image_url", "thumbnail")}),
        ("Pricing", {"fields": ("price", "currency")}),
        ("Visibility", {"fields": ("is_active",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Image")
    def thumbnail(self, obj: Product):
        if obj.image_url:
            return format_html(
                '<img src="{}" alt="{}" style="width:40px;height:40px;object-fit:cover;border-radius:4px;border:1px solid #e5e7eb;" />',
                obj.image_url,
                obj.title,
            )
        return "—"

    @admin.action(description="Activate selected products")
    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} product(s) activated.")

    @admin.action(description="Deactivate selected products")
    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} product(s) deactivated.")

    actions = ["make_active", "make_inactive"]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ("product", "quantity", "unit_price", "currency")
    autocomplete_fields = ("product",)


class OrderTransitionLogInline(admin.TabularInline):
    model = OrderTransitionLog
    can_delete = False
    extra = 0
    fields = ("created_at", "from_state", "to_state", "actor_user", "actor_label", "note")
    readonly_fields = ("created_at", "from_state", "to_state", "actor_user", "actor_label", "note")
    ordering = ("-created_at",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline, OrderTransitionLogInline]
    readonly_fields = ("created_at", "updated_at", "total")
    date_hierarchy = "created_at"
    list_per_page = 50
    list_display = ("id", "email", "status", "items_count", "total", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("email", "name", "street", "city", "zip")
    fieldsets = (
        ("Status", {"fields": ("status",)}),
        ("Contact", {"fields": ("email", "phone")}),
        ("Shipping", {"fields": ("name", "street", "city", "zip", "country")}),
        ("Totals", {"fields": ("total",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
    actions = ["mark_paid", "mark_cancelled", "apply_transition", "export_as_csv"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Annotate items_count for display; prefetch items to reduce queries on detail
        return qs.annotate(items_count=Count("items")).prefetch_related("items", "items__product")

    @admin.display(ordering="items_count", description="Items")
    def items_count(self, obj):
        return getattr(obj, "items_count", 0)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        order = form.instance
        order.compute_total()
        order.save(update_fields=["total"])

    def _apply_simple(self, request, queryset, to_state: str, label: str):
        if getattr(settings, "WORKFLOW_ENABLED", True):
            service = TransitionService()
            success = 0
            failed = []
            for order in queryset:
                res = service.transition(
                    order,
                    to_state,
                    actor_user=request.user,
                    actor_label="",
                    note=label,
                    idempotency_key=f"admin:{to_state}:{order.pk}",
                )
                if res.success:
                    success += 1
                else:
                    failed.append((order.pk, "; ".join(res.errors)))
            msg = f"{success} order(s) {label}."
            if failed:
                msg += f" {len(failed)} failed."
                self.message_user(request, msg, level=messages.WARNING)
            else:
                self.message_user(request, msg, level=messages.INFO)
        else:
            updated = queryset.update(status=to_state)
            self.message_user(request, f"{updated} order(s) {label}.", level=messages.INFO)

    @admin.action(description="Apply workflow transition…")
    def apply_transition(self, request, queryset):
        label_map = dict(OrderStatus.choices)
        service = TransitionService()
        # Union of available target states across selected orders
        targets = set()
        for o in queryset:
            for t in service.transitions_for_state(o.status):
                targets.add(t.to_state)
        choices = [(v, label_map.get(v, v.title())) for v in sorted(targets)]
        if not choices:
            self.message_user(request, "No available transitions for the selected orders.", level=messages.WARNING)
            return None

        if request.method == "POST" and request.POST.get("apply"):
            form = ApplyTransitionForm(request.POST, choices=choices)
            if form.is_valid():
                to_state = form.cleaned_data["target_state"]
                note = form.cleaned_data.get("note", "")
                dry_run = form.cleaned_data.get("dry_run", False)

                if not getattr(settings, "WORKFLOW_ENABLED", True):
                    updated = queryset.update(status=to_state)
                    self.message_user(
                        request,
                        f"{updated} order(s) updated to {label_map.get(to_state, to_state)} (legacy path).",
                        level=messages.INFO,
                    )
                    return None

                success, failed = 0, []
                for order in queryset:
                    res = service.transition(
                        order,
                        to_state,
                        actor_user=request.user,
                        actor_label="",
                        note=note,
                        idempotency_key=f"admin:apply:{to_state}:{order.pk}",
                        dry_run=dry_run,
                        request=request,
                    )
                    if res.success:
                        success += 1
                    else:
                        failed.append((order.pk, "; ".join(res.errors)))
                state_label = label_map.get(to_state, to_state)
                base = f"{success} order(s) validated" if dry_run else f"{success} order(s) transitioned"
                msg = f"{base} to {state_label}."
                if failed:
                    msg += f" {len(failed)} failed."
                    self.message_user(request, msg, level=messages.WARNING)
                else:
                    self.message_user(request, msg, level=messages.INFO)
                return None
        else:
            form = ApplyTransitionForm(choices=choices)

        context = dict(
            self.admin_site.each_context(request),
            title="Apply workflow transition",
            opts=self.model._meta,
            queryset=queryset,
            form=form,
            action="apply_transition",
        )
        return TemplateResponse(request, "admin/core/order/apply_transition.html", context)

    @admin.action(description="Mark selected orders as Paid")
    def mark_paid(self, request, queryset):
        self._apply_simple(request, queryset, OrderStatus.PAID, "marked as paid")

    @admin.action(description="Mark selected orders as Cancelled")
    def mark_cancelled(self, request, queryset):
        self._apply_simple(request, queryset, OrderStatus.CANCELLED, "cancelled")

    def has_delete_permission(self, request, obj=None):
        # Prevent deleting paid orders
        if obj and obj.status == OrderStatus.PAID:
            return False
        return super().has_delete_permission(request, obj)

    @admin.action(description="Export selected Orders to CSV")
    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="orders.csv"'
        writer = csv.writer(response)
        writer.writerow(["id", "email", "status", "total", "created_at"])
        for o in queryset:
            writer.writerow([o.id, o.email, o.status, o.total, o.created_at.isoformat()])
        return response
