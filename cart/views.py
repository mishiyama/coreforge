from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render

from products.models import Product

from .models import CartItem


@login_required
def cart_detail(request):

    cart_items = CartItem.objects.filter(
        user=request.user
    ).select_related(
        'product'
    )

    total = sum(
        item.subtotal
        for item in cart_items
    )

    return render(
        request,
        'cart/cart_detail.html',
        {
            'cart_items': cart_items,
            'total': total,
        }
    )


@login_required
def add_to_cart(request, product_id):

    if request.method != 'POST':
        return redirect('products:list')

    product = get_object_or_404(
        Product,
        id=product_id,
        is_active=True
    )

    if not product.is_in_stock:

        messages.error(
            request,
            f'{product.name} is currently out of stock.'
        )

        return redirect(
            product.get_absolute_url()
        )

    cart_item, created = CartItem.objects.get_or_create(
        user=request.user,
        product=product
    )

    if not created:

        if cart_item.quantity < product.stock:

            cart_item.quantity += 1
            cart_item.save()

        else:

            messages.warning(
                request,
                'You cannot add more than the available stock.'
            )

            return redirect('cart:detail')

    messages.success(
        request,
        f'{product.name} was added to your cart.'
    )

    return redirect('cart:detail')


@login_required
def update_cart(request, item_id):

    if request.method != 'POST':
        return redirect('cart:detail')

    cart_item = get_object_or_404(
        CartItem,
        id=item_id,
        user=request.user
    )

    try:

        quantity = int(
            request.POST.get('quantity', 1)
        )

    except (TypeError, ValueError):

        quantity = 1

    if quantity < 1:

        cart_item.delete()

    elif quantity > cart_item.product.stock:

        messages.warning(
            request,
            f'Only {cart_item.product.stock} items are available.'
        )

    else:

        cart_item.quantity = quantity
        cart_item.save()

    return redirect('cart:detail')


@login_required
def remove_from_cart(request, item_id):

    if request.method != 'POST':
        return redirect('cart:detail')

    cart_item = get_object_or_404(
        CartItem,
        id=item_id,
        user=request.user
    )

    cart_item.delete()

    messages.success(
        request,
        'Product removed from your cart.'
    )

    return redirect('cart:detail')