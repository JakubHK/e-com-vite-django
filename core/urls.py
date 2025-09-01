from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("product/<slug:slug>/", views.product_detail, name="product_detail"),
    path("cart/", views.cart_view, name="cart"),
    path("cart/badge", views.cart_badge, name="cart_badge"),
    path("cart/add", views.cart_add, name="cart_add"),
    path("cart/update", views.cart_update, name="cart_update"),
    path("cart/remove", views.cart_remove, name="cart_remove"),
    path("checkout/", views.checkout, name="checkout"),
    path("order/success/<int:order_id>/", views.order_success, name="order_success"),
]