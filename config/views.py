from django.http import JsonResponse
from django.shortcuts import render

from products.models import Product, Category


def health(request):

    return JsonResponse({
        'status': 'ok',
    })


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
