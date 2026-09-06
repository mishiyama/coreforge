from django.urls import path
from . import views


app_name = 'payments'


urlpatterns = [

    path(
        '<str:order_number>/esewa/',
        views.initiate_esewa_payment,
        name='initiate_esewa'
    ),

    path(
        '<str:order_number>/',
        views.payment_page,
        name='payment'
    ),

    path(
        '<str:order_number>/process/',
        views.process_payment,
        name='process'
    ),

    path(
        '<str:order_number>/success/',
        views.payment_success,
        name='success'
    ),

    path(
        '<str:order_number>/failed/',
        views.payment_failed,
        name='failed'
    ),
]