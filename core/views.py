from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.http import HttpResponse

from .models import Product, Category, Order, OrderItem
from .cart import get_cart
from .utils import hx_render


def home(request):
    # Redirect home to the canonical products listing
    return redirect("products")


def products_list(request):
    """
    Products listing with filtering and pagination.
    Full page render on normal requests, grid-only partial for HTMX.
    """
    qs = Product.objects.filter(is_active=True).select_related("category").order_by("title")

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))

    category_slug = (request.GET.get("category") or "").strip()
    selected_category = None
    if category_slug:
        selected_category = get_object_or_404(Category, slug=category_slug)
        qs = qs.filter(category=selected_category)

    page_number = request.GET.get("page") or 1
    paginator = Paginator(qs, 24)
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.order_by("title")

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "selected_category": selected_category,
        "category_slug": category_slug,
        "categories": categories,
        "wishlist": request.session.get("wishlist", []),
    }
    return hx_render(request, "core/products.html", "core/_product_grid.html", context)


def search_suggest(request):
    q = (request.GET.get("q") or "").strip()
    suggestions = []
    if q:
        suggestions = (
            Product.objects.filter(is_active=True, title__icontains=q)
            .order_by("title")[:8]
        )
    context = {"suggestions": suggestions, "q": q}
    return render(request, "core/_search_suggestions.html", context)


def product_detail(request, slug: str):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    in_wishlist = str(product.id) in request.session.get("wishlist", [])
    return render(request, "core/product_detail.html", {"product": product, "in_wishlist": in_wishlist})


@require_POST
def wishlist_toggle(request):
    product_id = request.POST.get("product_id")
    product = get_object_or_404(Product, id=product_id, is_active=True)

    wishlist = set(request.session.get("wishlist", []))
    pid = str(product.id)
    if pid in wishlist:
        wishlist.remove(pid)
        in_wishlist = False
    else:
        wishlist.add(pid)
        in_wishlist = True
    request.session["wishlist"] = list(wishlist)

    context = {"product": product, "in_wishlist": in_wishlist}
    resp = render(request, "components/_wishlist_button.html", context)
    if request.headers.get("HX-Request"):
        return resp
    return redirect(product.get_absolute_url())


def cart_view(request):
    cart = get_cart(request)
    return hx_render(request, "core/cart.html", "core/_cart_content.html", {"cart": cart})


def cart_badge(request):
    cart = get_cart(request)
    return render(request, "includes/_cart_badge.html", {"count": len(cart)})


@require_POST
def cart_add(request):
    cart = get_cart(request)
    product_id = request.POST.get("product_id")
    qty = int(request.POST.get("qty", 1) or 1)
    product = get_object_or_404(Product, id=product_id, is_active=True)
    cart.add(product, qty=qty)
    messages.success(request, f"Added “{product.title}” to cart.")
    resp = render(request, "includes/_cart_badge.html", {"count": len(cart)})
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

    # If coming from the cart page via HTMX, return the cart content partial
    if request.headers.get("HX-Request") and (request.POST.get("context") or "") == "page":
        resp = render(request, "core/_cart_content.html", {"cart": cart})
        resp["HX-Trigger"] = "cart-changed"
        return resp

    # Default: update navbar badge
    resp = render(request, "includes/_cart_badge.html", {"count": len(cart)})
    resp["HX-Trigger"] = "cart-changed"
    if request.headers.get("HX-Request"):
        return resp
    return redirect("cart")


@require_POST
def cart_remove(request):
    cart = get_cart(request)
    product_id = request.POST.get("product_id")
    cart.remove(product_id)

    # If coming from the cart page via HTMX, return the cart content partial
    if request.headers.get("HX-Request") and (request.POST.get("context") or "") == "page":
        resp = render(request, "core/_cart_content.html", {"cart": cart})
        resp["HX-Trigger"] = "cart-changed"
        return resp

    # Default: update navbar badge
    resp = render(request, "includes/_cart_badge.html", {"count": len(cart)})
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


def robots_txt(request):
    """
    Serve robots.txt with a pointer to sitemap.xml
    """
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")
