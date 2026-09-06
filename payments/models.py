from django.db import models
from orders.models import Order


class Payment(models.Model):

    PAYMENT_METHOD_CHOICES = [
        ('cod', 'Cash on Delivery'),
        ('esewa', 'eSewa'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='payment'
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES
    )

    transaction_id = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f'{self.order.order_number} - {self.payment_method}'