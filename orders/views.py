import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from cart.models import CartItem
from .forms import CheckoutForm
from .models import Order
from .models import OrderItem


@login_required
def checkout(request):

    cart_items = CartItem.objects.filter(
        user=request.user
    ).select_related(
        'product'
    )

    if not cart_items.exists():
        messages.info(request, 'Your cart is empty.')
        return redirect('cart:detail')

    subtotal = sum(
        item.subtotal
        for item in cart_items
    )
    delivery_charge = 0
    total = subtotal + delivery_charge
    form = CheckoutForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            order = form.save(commit=False)
            order.user = request.user
            order.order_number = f'NC-{uuid.uuid4().hex[:12].upper()}'
            order.subtotal = subtotal
            order.delivery_charge = delivery_charge
            order.total = total
            order.save()

            OrderItem.objects.bulk_create([
                OrderItem(
                    order=order,
                    product=item.product,
                    product_name=item.product.name,
                    product_price=item.product.final_price,
                    quantity=item.quantity,
                    subtotal=item.subtotal,
                )
                for item in cart_items
            ])
            cart_items.delete()

        return redirect(
            'payments:payment',
            order_number=order.order_number
        )

    return render(
        request,
        'orders/checkout.html',
        {
            'form': form,
            'cart_items': cart_items,
            'subtotal': subtotal,
            'delivery_charge': delivery_charge,
            'total': total,
        }
    )


@login_required
def order_list(request):

    orders = Order.objects.filter(
        user=request.user
    ).prefetch_related(
        'items'
    )

    return render(
        request,
        'orders/order_list.html',
        {
            'orders': orders,
        }
    )


@login_required
def order_detail(request, order_number):

    order = get_object_or_404(
        Order.objects.prefetch_related('items'),
        order_number=order_number,
        user=request.user
    )

    return render(
        request,
        'orders/order_detail.html',
        {
            'order': order,
        }
    )