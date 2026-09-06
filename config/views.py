from django.shortcuts import render

from products.models import Product, Category


def home(request):

    products = Product.objects.filter(
        is_active=True
    )[:8]

    categories = Category.objects.filter(
        is_active=True
    )

    return render(
        request,
        'home.html',
        {
            'products': products,
            'categories': categories,
        }
    )