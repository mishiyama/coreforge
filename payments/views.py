import base64
import binascii
import json
import uuid
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from orders.models import Order

from .models import Payment
from .utils import generate_esewa_signature
from .utils import verify_esewa_response_signature


@login_required
def payment_page(request, order_number):

    order = get_object_or_404(
        Order,
        order_number=order_number,
        user=request.user
    )

    return render(
        request,
        'payments/payment.html',
        {'order': order}
    )


@login_required
def process_payment(request, order_number):

    order = get_object_or_404(
        Order,
        order_number=order_number,
        user=request.user
    )

    if request.method != 'POST':
        return redirect(
            'payments:payment',
            order_number=order.order_number
        )

    if order.status in ['cancelled', 'delivered']:
        messages.error(request, 'This order cannot be paid.')
        return redirect(
            'orders:detail',
            order_number=order.order_number
        )

    payment_method = request.POST.get('payment_method')
    if payment_method not in ['cod', 'esewa']:
        messages.error(request, 'Select a valid payment method.')
        return redirect(
            'payments:payment',
            order_number=order.order_number
        )

    if payment_method == 'esewa':
        return redirect(
            'payments:initiate_esewa',
            order_number=order.order_number
        )

    order.payment_method = 'cod'
    order.payment_status = 'pending'
    order.save(update_fields=['payment_method', 'payment_status'])
    Payment.objects.update_or_create(
        order=order,
        defaults={
            'payment_method': 'cod',
            'transaction_id': None,
            'amount': order.total,
            'status': 'pending',
        }
    )
    return redirect(
        'orders:detail',
        order_number=order.order_number
    )


@login_required
def initiate_esewa_payment(request, order_number):

    order = get_object_or_404(
        Order,
        order_number=order_number,
        user=request.user
    )

    if order.status in ['cancelled', 'delivered']:
        messages.error(request, 'This order cannot be paid.')
        return redirect(
            'orders:detail',
            order_number=order.order_number
        )

    amount = Decimal(order.subtotal).quantize(Decimal('0.01'))
    tax_amount = Decimal('0.00')
    product_service_charge = Decimal('0.00')
    product_delivery_charge = Decimal(order.delivery_charge).quantize(
        Decimal('0.01')
    )
    total_amount = (
        amount
        + tax_amount
        + product_service_charge
        + product_delivery_charge
    ).quantize(Decimal('0.01'))
    amount_string = f'{float(amount):.2f}'
    tax_amount_string = f'{float(tax_amount):.2f}'
    service_charge_string = f'{float(product_service_charge):.2f}'
    delivery_charge_string = f'{float(product_delivery_charge):.2f}'
    total_amount_string = f'{float(total_amount):.2f}'
    transaction_uuid = str(uuid.uuid4())
    product_code = getattr(
        settings,
        'ESEWA_PRODUCT_CODE',
        'EPAYTEST'
    )
    payment_url = getattr(
        settings,
        'ESEWA_PAYMENT_URL',
        'https://rc-epay.esewa.com.np/api/epay/main/v2/form'
    )
    Payment.objects.update_or_create(
        order=order,
        defaults={
            'payment_method': 'esewa',
            'transaction_id': transaction_uuid,
            'amount': total_amount,
            'status': 'pending',
        }
    )
    order.payment_method = 'esewa'
    order.payment_status = 'pending'
    order.save(update_fields=['payment_method', 'payment_status'])

    success_url = request.build_absolute_uri(
        reverse('payments:success', args=[order.order_number])
    )
    failure_url = request.build_absolute_uri(
        reverse('payments:failed', args=[order.order_number])
    )
    esewa_fields = {
        'amount': amount_string,
        'tax_amount': tax_amount_string,
        'total_amount': total_amount_string,
        'transaction_uuid': transaction_uuid,
        'product_code': product_code,
        'product_service_charge': service_charge_string,
        'product_delivery_charge': delivery_charge_string,
        'success_url': success_url,
        'failure_url': failure_url,
        'signed_field_names': 'total_amount,transaction_uuid,product_code',
        'signature': generate_esewa_signature(
            total_amount,
            transaction_uuid,
            product_code
        ),
    }
    return render(
        request,
        'payments/payment.html',
        {
            'order': order,
            'esewa_payment': True,
            'esewa_payment_url': payment_url,
            'esewa_fields': esewa_fields,
        }
    )


@login_required
def payment_success(request, order_number):

    order = get_object_or_404(
        Order,
        order_number=order_number,
        user=request.user
    )
    encoded_data = request.GET.get('data')

    if not encoded_data:
        return redirect('payments:failed', order_number=order.order_number)

    try:
        decoded_data = base64.b64decode(encoded_data, validate=True).decode('utf-8')
        response_data = json.loads(decoded_data)
        total_amount = Decimal(response_data.get('total_amount', '0'))
    except (
        ValueError,
        TypeError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
        InvalidOperation,
    ):
        return redirect('payments:failed', order_number=order.order_number)

    payment = getattr(order, 'payment', None)
    valid_response = (
        response_data.get('status') == 'COMPLETE'
        and verify_esewa_response_signature(response_data)
        and payment is not None
        and response_data.get('transaction_uuid') == payment.transaction_id
        and response_data.get('product_code') == settings.ESEWA_PRODUCT_CODE
        and total_amount == order.total
    )
    if not valid_response:
        return redirect('payments:failed', order_number=order.order_number)

    order.payment_status = 'paid'
    order.save(update_fields=['payment_status'])
    payment.status = 'success'
    payment.save(update_fields=['status', 'updated_at'])
    return render(
        request,
        'payments/success.html',
        {'order': order}
    )


@login_required
def payment_failed(request, order_number):

    order = get_object_or_404(
        Order,
        order_number=order_number,
        user=request.user
    )
    order.payment_status = 'failed'
    order.save(update_fields=['payment_status'])
    Payment.objects.filter(order=order).update(status='failed')
    return render(
        request,
        'payments/failed.html',
        {'order': order}
    )