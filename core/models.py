from django.db import models
from django.urls import reverse
from django.conf import settings


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Category(TimeStampedModel):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)

    class Meta:
        ordering = ["title"]
        indexes = [
            models.Index(fields=["slug"]),
        ]

    def __str__(self) -> str:
        return self.title


class Product(TimeStampedModel):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    title = models.CharField(max_length=250)
    slug = models.SlugField(max_length=270, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")
    is_active = models.BooleanField(default=True)
    image_url = models.URLField(blank=True)

    class Meta:
        ordering = ["title"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["category", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self):
        return reverse("product_detail", kwargs={"slug": self.slug})


class OrderStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    SHIPPED = "shipped", "Shipped"
    FULFILLED = "fulfilled", "Fulfilled"
    REFUNDED = "refunded", "Refunded"
    RETURNED = "returned", "Returned"
    CANCELLED = "cancelled", "Cancelled"


class Order(TimeStampedModel):
    email = models.EmailField()
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING)

    # Simple shipping/contact fields for MVP
    name = models.CharField(max_length=200)
    street = models.CharField(max_length=200)
    city = models.CharField(max_length=120)
    zip = models.CharField(max_length=20)
    country = models.CharField(max_length=2, default="CZ")
    phone = models.CharField(max_length=30, blank=True)

    # Totals are computed; persist total for history
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Order #{self.pk or 'new'} - {self.email}"

    @property
    def currency(self) -> str:
        # Derive currency from first item if present, fallback to EUR
        first = self.items.first()
        return getattr(first, "currency", "EUR") if first else "EUR"

    def compute_total(self):
        from decimal import Decimal
        total = Decimal("0.00")
        for item in self.items.all():
            total += item.subtotal
        self.total = total
        return total


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")

    class Meta:
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["product"]),
        ]

    def __str__(self) -> str:
        return f"{self.product} x {self.quantity}"

    @property
    def subtotal(self):
        return self.unit_price * self.quantity


class OrderTransitionLog(TimeStampedModel):
    order = models.ForeignKey("Order", on_delete=models.CASCADE, related_name="transitions")
    from_state = models.CharField(max_length=20)
    to_state = models.CharField(max_length=20)
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    actor_label = models.CharField(max_length=200, blank=True)
    note = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    idempotency_key = models.CharField(max_length=64, blank=True, null=True, unique=True)

    class Meta:
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Order {self.order_id}: {self.from_state} → {self.to_state}"
