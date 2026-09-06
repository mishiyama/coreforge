from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from products.models import Product

from .models import WishlistItem


@login_required
def add_to_wishlist(request, product_id):

    if request.method != 'POST':
        return redirect('products:detail', slug=get_object_or_404(Product, id=product_id).slug)

    product = get_object_or_404(Product, id=product_id, is_active=True)
    WishlistItem.objects.get_or_create(user=request.user, product=product)
    messages.success(request, f'{product.name} was added to your wishlist.')
    return redirect('products:detail', slug=product.slug)


@login_required
def remove_from_wishlist(request, item_id):

    if request.method == 'POST':
        item = get_object_or_404(
            WishlistItem,
            id=item_id,
            user=request.user
        )
        item.delete()
        messages.success(request, 'Item removed from your wishlist.')

    return redirect('wishlist:detail')


@login_required
def wishlist_detail(request):

    items = WishlistItem.objects.filter(
        user=request.user
    ).select_related('product')

    return render(
        request,
        'wishlist/wishlist_detail.html',
        {'wishlist_items': items}
    )