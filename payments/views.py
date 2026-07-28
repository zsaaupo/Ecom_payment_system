import json
import logging

from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order

from .models import Payment
from .serializers import ConfirmPaymentSerializer, InitiatePaymentSerializer, PaymentSerializer
from .services import PaymentService
from .strategies import PaymentProviderError

logger = logging.getLogger("payments")


class InitiatePaymentView(APIView):
    """POST /api/payments/initiate/ {order_id, provider} -> starts a payment."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = get_object_or_404(Order, pk=serializer.validated_data["order_id"], user=request.user)

        try:
            payment, provider_result = PaymentService.initiate_payment(order, serializer.validated_data["provider"])
        except PaymentProviderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        data = PaymentSerializer(payment).data
        # surface provider-specific fields the client needs to complete payment
        for key in ("client_secret", "publishable_key", "bkash_url"):
            if key in provider_result:
                data[key] = provider_result[key]
        return Response(data, status=status.HTTP_201_CREATED)


class ConfirmPaymentView(APIView):
    """POST /api/payments/{id}/confirm/ - confirm/execute a pending payment."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk, order__user=request.user)
        serializer = ConfirmPaymentSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        payment = PaymentService.confirm_payment(payment, payload)
        return Response(PaymentSerializer(payment).data)


class QueryPaymentView(APIView):
    """GET /api/payments/{id}/query/ - query live status from the provider (bKash)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk, order__user=request.user)
        try:
            payment = PaymentService.query_payment(payment)
        except PaymentProviderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(PaymentSerializer(payment).data)


class PaymentDetailView(APIView):
    """GET /api/payments/{id}/ - view a single payment belonging to the current user."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk, order__user=request.user)
        return Response(PaymentSerializer(payment).data)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    """
    POST /api/payments/webhooks/stripe/
    Requirement (2.1.4 Stripe): "Webhook for payment updates."
    Stripe calls this directly (no user session), so auth is disabled here
    and replaced with signature verification instead.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        from .strategies import StripePaymentStrategy

        try:
            event = StripePaymentStrategy().verify_webhook(request)
        except PaymentProviderError as exc:
            logger.warning("Rejected Stripe webhook: %s", exc)
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        event_dict = event if isinstance(event, dict) else json.loads(str(event))
        PaymentService.handle_stripe_event(event_dict)
        return Response({"received": True})


@method_decorator(csrf_exempt, name="dispatch")
class BkashCallbackView(APIView):
    """
    GET/POST /payments/bkash/callback/ (also exposed under /api/payments/webhooks/bkash/)
    bKash redirects the user's browser here after they approve/cancel
    payment on bKash's hosted page, including ?paymentID=...&status=....
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def _is_browser(self, request):
        accept = request.META.get("HTTP_ACCEPT", "")
        return request.method == "GET" and ("text/html" in accept or "application/xhtml+xml" in accept or "*/*" in accept)

    def _handle(self, request):
        from .strategies import BkashPaymentStrategy

        try:
            event = BkashPaymentStrategy().verify_webhook(request)
        except PaymentProviderError as exc:
            logger.warning("Rejected bKash webhook: %s", exc)
            if self._is_browser(request):
                return redirect(f"{settings.FRONTEND_URL}/payment-bkash-return.html?status=failure")
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        payment = PaymentService.handle_bkash_event(event)
        if not payment:
            if self._is_browser(request):
                return redirect(f"{settings.FRONTEND_URL}/payment-bkash-return.html?status=failure")
            return Response({"detail": "Payment record not found."}, status=status.HTTP_404_NOT_FOUND)

        if self._is_browser(request):
            if payment.status == Payment.Status.SUCCESS:
                target_url = f"{settings.FRONTEND_URL}/order.html?id={payment.order_id}"
            else:
                target_url = f"{settings.FRONTEND_URL}/order.html?id={payment.order_id}&payment=failed"
            return redirect(target_url)

        return Response(PaymentSerializer(payment).data)

    def get(self, request):
        return self._handle(request)

    def post(self, request):
        return self._handle(request)
