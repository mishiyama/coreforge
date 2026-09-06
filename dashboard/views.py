from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from cart.models import CartItem
from orders.models import Order
from wishlist.models import WishlistItem


@login_required
def dashboard(request):

	return render(
		request,
		'dashboard/dashboard.html',
		{
			'order_count': Order.objects.filter(user=request.user).count(),
			'cart_count': CartItem.objects.filter(user=request.user).count(),
			'wishlist_count': WishlistItem.objects.filter(user=request.user).count(),
		}
	)
