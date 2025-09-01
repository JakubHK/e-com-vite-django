from __future__ import annotations

from decimal import Decimal
from typing import Iterator

from core.models import Product

CART_SESSION_ID = "cart"


class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(CART_SESSION_ID)
        if not cart:
            cart = {}
            self.session[CART_SESSION_ID] = cart
        self.cart = cart

    def _save(self):
        self.session[CART_SESSION_ID] = self.cart
        self.session.modified = True

    def add(self, product: Product, qty: int = 1, replace: bool = False):
        pid = str(product.id)
        if pid not in self.cart:
            self.cart[pid] = {
                "qty": 0,
                "unit_price": str(product.price),
                "currency": product.currency,
                "title": product.title,
                "slug": product.slug,
            }
        if replace:
            self.cart[pid]["qty"] = max(0, int(qty))
        else:
            self.cart[pid]["qty"] = max(0, int(self.cart[pid]["qty"]) + int(qty))
        if self.cart[pid]["qty"] <= 0:
            del self.cart[pid]
        self._save()

    def update(self, product_id: int | str, qty: int):
        pid = str(product_id)
        if pid in self.cart:
            self.cart[pid]["qty"] = max(0, int(qty))
            if self.cart[pid]["qty"] <= 0:
                del self.cart[pid]
            self._save()

    def remove(self, product_id: int | str):
        pid = str(product_id)
        if pid in self.cart:
            del self.cart[pid]
            self._save()

    def clear(self):
        self.session.pop(CART_SESSION_ID, None)
        self.session.modified = True
        self.cart = {}

    def __len__(self) -> int:
        return sum(int(item["qty"]) for item in self.cart.values())

    def items(self) -> Iterator[dict]:
        pids = [int(pid) for pid in self.cart.keys()]
        products = Product.objects.in_bulk(pids)
        for pid, data in self.cart.items():
            product = products.get(int(pid))
            if not product:
                # stale product; skip
                continue
            qty = int(data["qty"])
            unit_price = Decimal(data["unit_price"])
            yield {
                "product": product,
                "qty": qty,
                "unit_price": unit_price,
                "currency": data.get("currency", "EUR"),
                "subtotal": unit_price * qty,
            }

    def total_price(self) -> Decimal:
        total = Decimal("0.00")
        for item in self.items():
            total += item["subtotal"]
        return total

    def to_order_items(self):
        return [
            {
                "product": item["product"],
                "quantity": item["qty"],
                "unit_price": item["unit_price"],
                "currency": item["currency"],
            }
            for item in self.items()
        ]

    def is_empty(self) -> bool:
        return len(self) == 0


def get_cart(request) -> Cart:
    return Cart(request)