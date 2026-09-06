from django.urls import path

from . import views


app_name = 'accounts'


urlpatterns = [

    path(
        'register/',
        views.register_view,
        name='register'
    ),

    path(
        'login/',
        views.login_view,
        name='login'
    ),

    path(
        'profile/',
        views.profile_view,
        name='profile'
    ),

    path(
        'logout/',
        views.logout_view,
        name='logout'
    ),

    path(
        'password-reset/',
        views.password_reset_view,
        name='password_reset'
    ),

]