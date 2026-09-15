from django.core.management.base import BaseCommand
from payments.models import Payment
from payments.services import PaymentService
from payments.strategies import PaymentProviderError


class Command(BaseCommand):
    help = 'Query pending payments and apply verified results; never release unverified reservations.'

    def handle(self, *args, **options):
        for payment in Payment.objects.filter(status=Payment.Status.PENDING).iterator():
            try:
                result = PaymentService.query_payment(payment)
                self.stdout.write(f'Payment {payment.pk}: {result.status}')
            except PaymentProviderError:
                self.stderr.write(f'Payment {payment.pk}: provider unavailable; retry later.')
