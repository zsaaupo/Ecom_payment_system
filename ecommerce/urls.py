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

from payments.views import BkashCallbackView

urlpatterns = [
    path("admin/", admin.site.urls),

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
