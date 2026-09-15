"""
Strategy pattern implementation for the Payment System.

Architecture:
    - PaymentStrategy is the abstract interface every provider implements.
    - StripePaymentStrategy and BkashPaymentStrategy are concrete strategies.
    - PaymentContext is the unified interface used by the application, holding
      a strategy instance and delegating requests to it. Adding a new provider
      only requires implementing a new PaymentStrategy class and registering it
      in STRATEGY_REGISTRY.
"""
import abc
import logging

import requests
import stripe
from django.conf import settings

logger = logging.getLogger("payments")


class PaymentProviderError(Exception):
    """Raised when a provider call fails or is misconfigured."""


class PaymentStrategy(abc.ABC):
    """Common interface every payment provider strategy must implement."""

    name = None

    @abc.abstractmethod
    def initiate(self, order):
        """
        Start a payment for `order`.
        Returns a dict with at least:
            {"transaction_id": str, "status": "pending"|"success"|"failed",
             "raw_response": dict, ...provider-specific extras}
        """
        raise NotImplementedError

    @abc.abstractmethod
    def confirm(self, transaction_id, payload=None):
        """
        Confirm/execute a previously-initiated payment.
        Returns a dict: {"status": "success"|"failed"|"pending", "raw_response": dict}
        """
        raise NotImplementedError

    def query(self, transaction_id):
        """Optional: query current status from the provider. Default: not supported."""
        raise PaymentProviderError(f"{self.name} does not support status queries.")

    def verify_webhook(self, request):
        """Optional: verify an inbound webhook/callback. Returns parsed event dict."""
        raise NotImplementedError(f"{self.name} does not support webhook verification.")


class StripePaymentStrategy(PaymentStrategy):
    """
    Stripe integration using PaymentIntents (test + live mode - the SAME
    code path is used for both; only the API key differs, per Stripe's own
    design, satisfying the "test + live mode" deliverable).
    """
    name = "stripe"

    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY

    def initiate(self, order):
        """Create a PaymentIntent and return client details for checkout."""
        if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_PUBLISHABLE_KEY:
            raise PaymentProviderError(
                "Stripe is not configured. Set STRIPE_SECRET_KEY in your .env file."
            )
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(order.total_amount * 100),  # Stripe uses the smallest currency unit
                currency=order.currency.lower(),
                idempotency_key=f'order-{order.pk}-stripe',
                metadata={"order_id": str(order.id)},
                automatic_payment_methods={"enabled": True},
            )
        except stripe.error.StripeError as exc:
            logger.exception("Stripe PaymentIntent creation failed for order %s", order.id)
            raise PaymentProviderError(str(exc)) from exc

        return {
            "transaction_id": intent.id,
            "status": "pending",
            "client_secret": intent.client_secret,
            "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
            "raw_response": intent.to_dict() if hasattr(intent, "to_dict") else dict(intent),
        }

    def confirm(self, transaction_id, payload=None):
        """Re-fetch the PaymentIntent to confirm its current status."""
        try:
            intent = stripe.PaymentIntent.retrieve(transaction_id)
        except stripe.error.StripeError as exc:
            raise PaymentProviderError(str(exc)) from exc

        status_map = {
            "succeeded": "success",
            "processing": "pending",
            "requires_payment_method": "pending",
            "requires_action": "pending",
            "canceled": "failed",
        }
        return {
            "status": status_map.get(intent.status, "pending"),
            "raw_response": intent.to_dict() if hasattr(intent, "to_dict") else dict(intent),
        }

    def query(self, transaction_id):
        return self.confirm(transaction_id)

    def verify_webhook(self, request):
        """
        Verifies the `Stripe-Signature` header per Stripe's webhook specification.
        """
        payload = request.body
        sig_header = request.headers.get("Stripe-Signature", "")
        if not settings.STRIPE_WEBHOOK_SECRET:
            raise PaymentProviderError("STRIPE_WEBHOOK_SECRET is not configured.")
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
        except (ValueError, stripe.error.SignatureVerificationError) as exc:
            raise PaymentProviderError(f"Invalid Stripe webhook signature: {exc}") from exc
        return event


class BkashPaymentStrategy(PaymentStrategy):
    """
    bKash Tokenized Checkout (sandbox + live - same code path, only
    BKASH_BASE_URL / credentials differ between environments).
    Flow: grant token -> create payment -> (user pays on bKash's page) ->
    execute payment -> (optionally) query payment.
    """
    name = "bkash"

    def __init__(self):
        self.base_url = settings.BKASH_BASE_URL.rstrip("/")
        self.app_key = settings.BKASH_APP_KEY
        self.app_secret = settings.BKASH_APP_SECRET
        self.username = settings.BKASH_USERNAME
        self.password = settings.BKASH_PASSWORD

    def _require_config(self):
        if not all([self.app_key, self.app_secret, self.username, self.password]):
            raise PaymentProviderError(
                "bKash is not configured. Set BKASH_APP_KEY, BKASH_APP_SECRET, "
                "BKASH_USERNAME and BKASH_PASSWORD in your .env file."
            )

    def _grant_token(self):
        self._require_config()
        url = f"{self.base_url}/tokenized/checkout/token/grant"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "username": self.username,
            "password": self.password,
        }
        body = {"app_key": self.app_key, "app_secret": self.app_secret}
        try:
            response = requests.post(url, json=body, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise PaymentProviderError('bKash authentication is temporarily unavailable.') from exc
        if "id_token" not in data:
            raise PaymentProviderError(f"bKash token grant failed: {data}")
        return data["id_token"]

    def _auth_headers(self, id_token):
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": id_token,
            "X-APP-Key": self.app_key,
        }

    def initiate(self, order):
        """Create a bKash tokenized payment session."""
        if order.currency != 'BDT':
            raise PaymentProviderError('bKash requires an order priced in BDT.')
        id_token = self._grant_token()
        url = f"{self.base_url}/tokenized/checkout/create"
        body = {
            "mode": "0011",
            "payerReference": str(order.user_id),
            "callbackURL": settings.BKASH_CALLBACK_URL,
            "amount": str(order.total_amount),
            "currency": "BDT",
            "intent": "sale",
            "merchantInvoiceNumber": f"ORDER-{order.id}",
        }
        try:
            response = requests.post(url, json=body, headers=self._auth_headers(id_token), timeout=15)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise PaymentProviderError(f"bKash create-payment request failed: {exc}") from exc

        payment_id = data.get("paymentID")
        if not payment_id or not data.get('bkashURL') or str(data.get('statusCode', '0000')) != '0000':
            raise PaymentProviderError(f"bKash did not return a paymentID: {data}")

        return {
            "transaction_id": payment_id,
            "status": "pending",
            "bkash_url": data.get("bkashURL"),
            "raw_response": data,
        }

    def confirm(self, transaction_id, payload=None):
        """Execute the payment after the user completes it on bKash's page."""
        id_token = self._grant_token()
        url = f"{self.base_url}/tokenized/checkout/execute"
        try:
            response = requests.post(
                url, json={"paymentID": transaction_id}, headers=self._auth_headers(id_token), timeout=15
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError):
            return self.query(transaction_id)

        status_code = str(data.get("statusCode", ""))
        trx_status = data.get("transactionStatus")

        if status_code == "0000" and trx_status == "Completed":
            res_status = "success"
        elif status_code != '0000':
            return self.query(transaction_id)
        elif trx_status in ("Failed", "Cancelled", "Canceled"):
            res_status = "failed"
        else:
            res_status = "pending"

        return {
            "status": res_status,
            "raw_response": data,
        }

    def query(self, transaction_id):
        """Query payment status directly from bKash API."""
        id_token = self._grant_token()
        url = f"{self.base_url}/tokenized/checkout/payment/status"
        try:
            response = requests.post(
                url, json={"paymentID": transaction_id}, headers=self._auth_headers(id_token), timeout=15
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise PaymentProviderError(f"bKash query-payment request failed: {exc}") from exc

        status_code = str(data.get("statusCode", ""))
        trx_status = data.get("transactionStatus")

        if status_code == "0000" and trx_status == "Completed":
            res_status = "success"
        elif status_code not in ('', '0000'):
            raise PaymentProviderError('bKash could not verify the payment status. Please retry.')
        elif trx_status in ("Failed", "Cancelled", "Canceled", "Expired"):
            res_status = "failed"
        else:
            res_status = "pending"

        return {
            "status": res_status,
            "raw_response": data,
        }

    def verify_webhook(self, request):
        """
        Parses and verifies an inbound bKash callback or IPN webhook payload.
        Expects query parameters or JSON body containing 'paymentID' and 'status'.
        """
        if request.method == 'POST' and not hasattr(request.data, 'get'):
            raise PaymentProviderError('Expected an object containing paymentID and status.')
        payment_id = request.GET.get("paymentID") or (
            request.data.get("paymentID") if hasattr(request, "data") and request.data else None
        )
        bkash_status = request.GET.get("status") or (
            request.data.get("status") if hasattr(request, "data") and request.data else None
        )

        if not payment_id:
            raise PaymentProviderError("Missing paymentID in bKash webhook request.")

        return {
            "payment_id": payment_id,
            "status": bkash_status or "success",
            "raw": dict(request.GET.items()) if request.method == "GET" else getattr(request, "data", {}),
        }


STRATEGY_REGISTRY = {
    StripePaymentStrategy.name: StripePaymentStrategy,
    BkashPaymentStrategy.name: BkashPaymentStrategy,
    # To add a new provider: write a class implementing PaymentStrategy,
    # then register it here. No other code needs to change.
}


class PaymentContext:
    """The single entry point the rest of the app uses to talk to *any*
    payment provider, per the Strategy design pattern."""

    def __init__(self, provider: str):
        strategy_cls = STRATEGY_REGISTRY.get(provider)
        if not strategy_cls:
            raise PaymentProviderError(f"Unknown payment provider '{provider}'.")
        self.provider = provider
        self.strategy: PaymentStrategy = strategy_cls()

    def initiate(self, order):
        return self.strategy.initiate(order)

    def confirm(self, transaction_id, payload=None):
        return self.strategy.confirm(transaction_id, payload)

    def query(self, transaction_id):
        return self.strategy.query(transaction_id)

    def verify_webhook(self, request):
        return self.strategy.verify_webhook(request)
