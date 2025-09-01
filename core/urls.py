from django.urls import path
from django.contrib.sitemaps.views import sitemap
from . import views
from .sitemaps import ProductSitemap, StaticViewSitemap

sitemaps = {
    "products": ProductSitemap,
    "static": StaticViewSitemap,
}

urlpatterns = [
    path("", views.home, name="home"),
    path("products/", views.products_list, name="products"),
    path("search/suggest/", views.search_suggest, name="search_suggest"),
    path("wishlist/toggle/", views.wishlist_toggle, name="wishlist_toggle"),

    path("product/<slug:slug>/", views.product_detail, name="product_detail"),

    path("cart/", views.cart_view, name="cart"),
    path("cart/badge", views.cart_badge, name="cart_badge"),
    path("cart/add", views.cart_add, name="cart_add"),
    path("cart/update", views.cart_update, name="cart_update"),
    path("cart/remove", views.cart_remove, name="cart_remove"),
    path("checkout/", views.checkout, name="checkout"),
    path("order/success/<int:order_id>/", views.order_success, name="order_success"),

    # SEO: robots.txt and sitemap.xml
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
]