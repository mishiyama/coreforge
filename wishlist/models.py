from django.conf import settings
from django.db import models

from products.models import Product


class WishlistItem(models.Model):

	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='wishlist_items'
	)
	product = models.ForeignKey(
		Product,
		on_delete=models.CASCADE,
		related_name='wishlist_items'
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']
		constraints = [
			models.UniqueConstraint(
				fields=['user', 'product'],
				name='unique_user_wishlist_product'
			)
		]
