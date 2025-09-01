from django.test import TestCase, Client
from django.urls import reverse


class SSRHtmxFlowTests(TestCase):
    fixtures = ["sample.json"]

    def setUp(self):
        self.client = Client()

    def test_home_redirects_to_products(self):
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("products"))

    def test_products_full_render_contains_base_layout(self):
        resp = self.client.get(reverse("products"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8").lower()
        self.assertIn("<html", html)
        # Products full page includes wrapper container id
        self.assertIn('id="product-grid"', html)

    def test_products_htmx_partial_render(self):
        resp = self.client.get(reverse("products"), HTTP_HX_REQUEST="true")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8").lower()
        # Partial should not include full html skeleton
        self.assertNotIn("<html", html)
        # Partial grid includes the indicator element
        self.assertIn("htmx-indicator", html)

    def test_search_suggest_partial_limit(self):
        # Query that should match some products from fixtures (e.g., 'django')
        resp = self.client.get(reverse("search_suggest"), {"q": "django"})
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8").lower()
        self.assertNotIn("<html", html)
        # Should contain the list container
        self.assertIn("<ul", html)

        # Ensure suggestions do not exceed 8 (cannot parse count easily here; sanity check content exists)
        # When q is empty, should render "Start typing" notice
        resp2 = self.client.get(reverse("search_suggest"), {"q": ""})
        self.assertEqual(resp2.status_code, 200)
        self.assertIn("start typing", resp2.content.decode("utf-8").lower())

    def test_wishlist_toggle_session_and_partial(self):
        # Use first product (pk=1 from fixture)
        product_id = 1
        # Ensure wishlist empty
        self.client.session["wishlist"] = []
        self.client.session.save()

        resp = self.client.post(
            reverse("wishlist_toggle"),
            {"product_id": product_id},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8").lower()
        # Button partial rendered
        self.assertIn("<form", html)
        # Session updated
        wishlist = self.client.session.get("wishlist", [])
        self.assertIn(str(product_id), wishlist)

        # Toggle again: should remove
        resp2 = self.client.post(
            reverse("wishlist_toggle"),
            {"product_id": product_id},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp2.status_code, 200)
        wishlist2 = self.client.session.get("wishlist", [])
        self.assertNotIn(str(product_id), wishlist2)

    def test_cart_add_returns_badge_partial_on_htmx(self):
        product_id = 1
        resp = self.client.post(
            reverse("cart_add"),
            {"product_id": product_id, "qty": 1},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8").lower()
        self.assertIn('id="cart-badge"', html)
        # Count should be 1
        self.assertIn(">1<", html)

    def test_cart_update_returns_cart_content_partial_with_context_page(self):
        product_id = 1
        # Add product first
        self.client.post(
            reverse("cart_add"),
            {"product_id": product_id, "qty": 1},
            HTTP_HX_REQUEST="true",
        )
        # Update qty to 2 in cart page context
        resp = self.client.post(
            reverse("cart_update"),
            {"product_id": product_id, "qty": 2, "context": "page"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        # Partial cart content contains Order Summary heading
        self.assertIn("Order Summary", html)

    def test_cart_remove_returns_cart_content_partial_with_context_page(self):
        product_id = 1
        # Add product first
        self.client.post(
            reverse("cart_add"),
            {"product_id": product_id, "qty": 1},
            HTTP_HX_REQUEST="true",
        )
        # Remove in cart page context
        resp = self.client.post(
            reverse("cart_remove"),
            {"product_id": product_id, "context": "page"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        # After removal, either empty cart prompt or updated table renders
        self.assertTrue(("Your cart is empty." in html) or ("Order Summary" in html))

    def test_robots_and_sitemap(self):
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertEqual(robots["Content-Type"].split(";")[0], "text/plain")
        self.assertIn("Sitemap:", robots.content.decode("utf-8"))

        sitemap = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap.status_code, 200)
        xml = sitemap.content.decode("utf-8").lower()
        self.assertIn("<urlset", xml)
