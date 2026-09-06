import base64
import hashlib
import hmac

from django.conf import settings


def generate_esewa_signature(
    total_amount,
    transaction_uuid,
    product_code=None
):
    """Create the ePay v2 request signature required by eSewa."""
    total_amount = f'{float(total_amount):.2f}'
    product_code = product_code or getattr(
        settings,
        'ESEWA_PRODUCT_CODE',
        'EPAYTEST'
    )
    message = f'total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}'
    secret_key = getattr(
        settings,
        'ESEWA_SECRET_KEY',
        '8gBm/:&EnhH.1/q'
    )
    digest = hmac.new(
        secret_key.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()
    return base64.b64encode(digest).decode('utf-8')


def verify_esewa_response_signature(data):
    """Verify a callback using eSewa's signed_field_names payload."""
    signed_field_names = data.get('signed_field_names', '')
    if not signed_field_names or not data.get('signature'):
        return False

    message = ','.join(
        f'{field}={data.get(field, "")}'
        for field in signed_field_names.split(',')
    )
    secret_key = getattr(
        settings,
        'ESEWA_SECRET_KEY',
        '8gBm/:&EnhH.1/q'
    )
    digest = hmac.new(
        secret_key.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()
    expected = base64.b64encode(digest).decode('utf-8')
    return hmac.compare_digest(expected, data['signature'])
