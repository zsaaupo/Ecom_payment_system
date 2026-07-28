from django.urls import path

from . import views

app_name = "payments_api"

urlpatterns = [
    path("initiate/", views.InitiatePaymentView.as_view(), name="initiate"),
    path("<int:pk>/", views.PaymentDetailView.as_view(), name="detail"),
    path("<int:pk>/confirm/", views.ConfirmPaymentView.as_view(), name="confirm"),
    path("<int:pk>/query/", views.QueryPaymentView.as_view(), name="query"),
    path("webhooks/stripe/", views.StripeWebhookView.as_view(), name="stripe_webhook"),
    path("webhooks/bkash/", views.BkashCallbackView.as_view(), name="bkash_webhook"),
    path("bkash/callback/", views.BkashCallbackView.as_view(), name="bkash_callback"),
]
