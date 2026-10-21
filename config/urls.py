from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve

from . import views


urlpatterns = [

    path(
        'healthz/',
        views.health,
        name='health'
    ),

    path(
        '',
        views.home,
        name='home'
    ),

    path(
        'admin/',
        admin.site.urls
    ),

    path(
        'accounts/',
        include('accounts.urls')
    ),

    path(
        'products/',
        include('products.urls')
    ),

    path(
        'cart/',
        include('cart.urls')
    ),

    path(
        'orders/',
        include('orders.urls')
    ),

    path(
        'wishlist/',
        include('wishlist.urls')
    ),

    path(
    'payments/',
    include('payments.urls')
    ),

    path(
        'dashboard/',
        include('dashboard.urls')
    ),

    path(
        'reviews/',
        include('reviews.urls')
    ),
]


if settings.DEBUG or getattr(settings, "SERVE_MEDIA_LOCALLY", False):

    urlpatterns += [
        re_path(
            r'^media/(?P<path>.*)$',
            serve,
            {'document_root': settings.MEDIA_ROOT},
        ),
    ]