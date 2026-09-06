from django.conf import settings
from django.db import models
from django.urls import reverse

from products.models import Product


class Order(models.Model):

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('cod', 'Cash on Delivery'),
        ('esewa', 'eSewa'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='orders'
    )

    order_number = models.CharField(
        max_length=30,
        unique=True
    )

    # Customer information
    full_name = models.CharField(
        max_length=150
    )

    email = models.EmailField()

    phone = models.CharField(
        max_length=20
    )

    # Shipping information
    address = models.TextField()

    city = models.CharField(
        max_length=100
    )

    province = models.CharField(
        max_length=100
    )

    postal_code = models.CharField(
        max_length=20,
        blank=True
    )

    # Amounts
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    delivery_charge = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    # Payment
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='cod'
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
    )

    # Order status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    notes = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.order_number

    def get_absolute_url(self):
        return reverse(
            'orders:detail',
            kwargs={'order_number': self.order_number}
        )


class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT
    )

    product_name = models.CharField(
        max_length=200
    )

    product_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    quantity = models.PositiveIntegerField()

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.product_name} × {self.quantity}'

