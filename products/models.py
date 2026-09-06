from django.db import models
from django.urls import reverse


class Category(models.Model):

    name = models.CharField(
        max_length=100
    )

    slug = models.SlugField(
        unique=True
    )

    description = models.TextField(
        blank=True
    )

    image = models.ImageField(
        upload_to='categories/',
        blank=True,
        null=True
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f"{reverse('products:list')}?category={self.pk}"

class Product(models.Model):

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products'
    )

    name = models.CharField(
        max_length=200
    )

    slug = models.SlugField(max_length=200, unique=True)

    description = models.TextField()

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    discount_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )

    stock = models.PositiveIntegerField(
        default=0
    )

    image = models.ImageField(
        upload_to='products/'
    )

    brand = models.CharField(
        max_length=100,
        blank=True
    )

    sku = models.CharField(
    max_length=50,
    unique=True,
    null=True,
    blank=True
    )

    is_active = models.BooleanField(
        default=True
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
        return self.name

    @property
    def final_price(self):

        if self.discount_price:
            return self.discount_price

        return self.price

    @property
    def is_in_stock(self):
        return self.stock > 0

    def get_absolute_url(self):

        return reverse(
            'products:detail',
            kwargs={'slug': self.slug}
        )