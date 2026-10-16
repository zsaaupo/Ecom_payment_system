"""
Root URL configuration.

Frontend (server-rendered HTML/CSS/JS) lives at the root paths.
REST APIs (used by Postman / the frontend's JS fetch calls) are namespaced
under /api/.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from payments.views import BkashCallbackView

urlpatterns = [
    path("admin/", admin.site.urls),

    # Storefront pages (served via Django template system)
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
    path("index.html", TemplateView.as_view(template_name="index.html"), name="index"),
    path("product.html", TemplateView.as_view(template_name="product.html"), name="product"),
    path("cart.html", TemplateView.as_view(template_name="cart.html"), name="cart"),
    path("checkout.html", TemplateView.as_view(template_name="checkout.html"), name="checkout"),
    path("login.html", TemplateView.as_view(template_name="login.html"), name="login"),
    path("register.html", TemplateView.as_view(template_name="register.html"), name="register"),
    path("account.html", TemplateView.as_view(template_name="account.html"), name="account"),
    path("orders.html", TemplateView.as_view(template_name="orders.html"), name="orders"),
    path("order.html", TemplateView.as_view(template_name="order.html"), name="order"),
    path("payment-stripe.html", TemplateView.as_view(template_name="payment-stripe.html"), name="payment_stripe"),
    path("payment-bkash.html", TemplateView.as_view(template_name="payment-bkash.html"), name="payment_bkash"),
    path(
        "payment-bkash-return.html",
        TemplateView.as_view(template_name="payment-bkash-return.html"),
        name="payment_bkash_return",
    ),

    # REST API (JSON) - see docs/postman_collection.json
    path("api/auth/", include("users.urls")),
    path("api/products/", include("products.urls")),
    path("api/orders/", include("orders.urls")),
    path("api/payments/", include("payments.urls")),

    # bKash callback route aliases without /api/ prefix
    path("payments/bkash/callback/", BkashCallbackView.as_view(), name="root_bkash_callback"),
    path("payments/webhooks/bkash/", BkashCallbackView.as_view(), name="root_bkash_webhook"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
