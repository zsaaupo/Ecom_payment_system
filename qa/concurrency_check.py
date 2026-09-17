"""Exercise real SQLite writer contention using an isolated on-disk database."""
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    work = root.parent / 'work'
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='sqlite-qa-', dir=work) as directory:
        os.environ['DJANGO_DB_DIR'] = directory
        os.environ['DJANGO_SETTINGS_MODULE'] = 'ecommerce.settings'
        os.environ['REDIS_URL'] = ''
        import django
        django.setup()
        from django.core.management import call_command
        from django.core.exceptions import ValidationError
        from django.db import connections
        from orders.models import Order, OrderItem
        from payments.models import Payment
        from payments.services import PaymentService
        from payments.strategies import StripePaymentStrategy
        from products.models import Product
        from users.models import User

        call_command('migrate', verbosity=0)
        user = User.objects.create_user(username='concurrency', email='concurrency@example.test')
        product = Product.objects.create(name='Last units', sku='LAST', price='10.00', stock=2)
        orders = []
        for _ in range(2):
            order = Order.objects.create(user=user, total_amount='20.00')
            OrderItem.objects.create(order=order, product=product, quantity=2, price='10.00', subtotal='20.00')
            orders.append(order)

        def initiate(order):
            try:
                return PaymentService.initiate_payment(order, 'stripe')[0].pk
            except ValidationError:
                return None
            finally:
                connections.close_all()

        with patch.object(StripePaymentStrategy, 'initiate', return_value={'transaction_id': 'concurrent', 'raw_response': {}}):
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(initiate, orders))
        assert sum(result is not None for result in results) == 1, results
        product.refresh_from_db()
        assert product.stock == 0
        payment = Payment.objects.get()

        def confirm(_):
            try:
                return PaymentService._apply_result(payment, {'status': 'success'}).status
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            assert list(executor.map(confirm, range(2))) == ['success', 'success']
        product.refresh_from_db()
        payment.order.refresh_from_db()
        assert product.stock == 0
        assert payment.order.status == 'paid'
        assert not payment.order.needs_review
        connections.close_all()
    print('PASS: concurrent checkout admits one payment; concurrent confirmations deduct stock once.')


if __name__ == '__main__':
    main()
