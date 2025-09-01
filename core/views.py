from django.contrib import messages
from django.db import transaction
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import Product, Order, OrderItem
from .cart import get_cart


def home(request):
    products = (
        Product.objects.filter(is_active=True)
        .select_related("category")
        .order_by("title")
    )
    return render(request, "core/home.html", {"products": products})


def product_detail(request, slug: str):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    return render(request, "core/product_detail.html", {"product": product})


def cart_view(request):
    cart = get_cart(request)
    return render(request, "core/cart.html", {"cart": cart})


def cart_badge(request):
    cart = get_cart(request)
    return render(request, "includes/cart_badge.html", {"count": len(cart)})


@require_POST
def cart_add(request):
    cart = get_cart(request)
    product_id = request.POST.get("product_id")
    qty = int(request.POST.get("qty", 1) or 1)
    product = get_object_or_404(Product, id=product_id, is_active=True)
    cart.add(product, qty=qty)
    messages.success(request, f"Added “{product.title}” to cart.")
    resp = render(request, "includes/cart_badge.html", {"count": len(cart)})
    resp["HX-Trigger"] = "cart-changed"
    if request.headers.get("HX-Request"):
        return resp
    return redirect("cart")


@require_POST
def cart_update(request):
    cart = get_cart(request)
    product_id = request.POST.get("product_id")
    qty = int(request.POST.get("qty", 1) or 1)
    cart.update(product_id, qty)
    resp = render(request, "includes/cart_badge.html", {"count": len(cart)})
    resp["HX-Trigger"] = "cart-changed"
    if request.headers.get("HX-Request"):
        return resp
    return redirect("cart")


@require_POST
def cart_remove(request):
    cart = get_cart(request)
    product_id = request.POST.get("product_id")
    cart.remove(product_id)
    resp = render(request, "includes/cart_badge.html", {"count": len(cart)})
    resp["HX-Trigger"] = "cart-changed"
    if request.headers.get("HX-Request"):
        return resp
    return redirect("cart")


def checkout(request):
    cart = get_cart(request)
    if request.method == "POST":
        if cart.is_empty():
            messages.error(request, "Your cart is empty.")
            return redirect("cart")

        email = (request.POST.get("email") or "").strip()
        name = (request.POST.get("name") or "").strip()
        street = (request.POST.get("street") or "").strip()
        city = (request.POST.get("city") or "").strip()
        zip_code = (request.POST.get("zip") or "").strip()
        country = (request.POST.get("country") or "CZ").strip()
        phone = (request.POST.get("phone") or "").strip()

        if not all([email, name, street, city, zip_code, country]):
            messages.error(request, "Please complete all required fields.")
            return redirect("checkout")

        with transaction.atomic():
            order = Order.objects.create(
                email=email,
                name=name,
                street=street,
                city=city,
                zip=zip_code,
                country=country,
                phone=phone,
            )
            for item in cart.to_order_items():
                OrderItem.objects.create(
                    order=order,
                    product=item["product"],
                    quantity=item["quantity"],
                    unit_price=item["unit_price"],
                    currency=item["currency"],
                )
            order.compute_total()
            order.save()

        cart.clear()
        return redirect("order_success", order_id=order.id)

    return render(request, "core/checkout.html", {"cart": cart})


def order_success(request, order_id: int):
    order = get_object_or_404(Order, id=order_id)
    return render(request, "core/order_success.html", {"order": order})
