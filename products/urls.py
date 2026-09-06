from django.urls import path

from . import views


app_name = "products"


urlpatterns = [

    path(
        'categories/',
        views.category_list,
        name='category_list'
    ),

    path(
        'categories/<slug:slug>/',
        views.category_detail,
        name='category_detail'
    ),

    path(
        "",
        views.product_list,
        name="list"
    ),

    path(
        "<slug:slug>/",
        views.product_detail,
        name="detail"
    ),

]