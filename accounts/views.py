from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm, ProfileForm, RegisterForm
from .models import CustomerProfile


def register_view(request):

    if request.user.is_authenticated:
        return redirect('products:list')

    if request.method == 'POST':

        form = RegisterForm(request.POST)

        if form.is_valid():

            user = form.save()

            # Make sure every registered user has a profile.
            CustomerProfile.objects.get_or_create(
                user=user
            )

            login(request, user)

            messages.success(
                request,
                'Your account has been created successfully.'
            )

            return redirect('products:list')

    else:

        form = RegisterForm()

    return render(
        request,
        'accounts/register.html',
        {
            'form': form
        }
    )


def login_view(request):

    if request.user.is_authenticated:
        return redirect('products:list')

    if request.method == 'POST':

        form = LoginForm(request.POST)

        if form.is_valid():

            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            user = authenticate(
                request,
                username=username,
                password=password
            )

            if user is not None:

                login(request, user)

                # Check if "Remember Me" was selected in the form/request
                remember_me = request.POST.get('remember_me') or form.cleaned_data.get('remember_me')

                if remember_me:
                    # Keep session active for 30 days (in seconds)
                    request.session.set_expiry(2592000)
                else:
                    # Session expires when the browser closes
                    request.session.set_expiry(0)

                messages.success(
                    request,
                    'You have been logged in successfully.'
                )

                next_url = request.POST.get('next') or request.GET.get(
                    'next'
                )

                if next_url and url_has_allowed_host_and_scheme(
                    url=next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)

                return redirect('products:list')

            form.add_error(
                None,
                'Invalid username or password.'
            )

    else:

        form = LoginForm()

    return render(
        request,
        'accounts/login.html',
        {
            'form': form
        }
    )


@login_required
def profile_view(request):

    profile, created = CustomerProfile.objects.get_or_create(
        user=request.user
    )

    if request.method == 'POST':

        form = ProfileForm(
            request.POST,
            request.FILES
        )

        if form.is_valid():

            request.user.first_name = form.cleaned_data[
                'first_name'
            ]

            request.user.last_name = form.cleaned_data[
                'last_name'
            ]

            request.user.email = form.cleaned_data[
                'email'
            ]

            request.user.save(
                update_fields=[
                    'first_name',
                    'last_name',
                    'email',
                ]
            )

            profile.phone = form.cleaned_data[
                'phone'
            ]

            if form.cleaned_data.get('profile_image'):

                profile.profile_image = form.cleaned_data[
                    'profile_image'
                ]

            profile.save()

            messages.success(
                request,
                'Your profile has been updated successfully.'
            )

            return redirect(
                'accounts:profile'
            )

    else:

        form = ProfileForm(
            initial={
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'email': request.user.email,
                'phone': profile.phone,
            }
        )

    return render(
        request,
        'accounts/profile.html',
        {
            'form': form,
            'profile': profile,
        }
    )


def logout_view(request):

    if request.method == 'POST':

        logout(request)

        messages.success(
            request,
            'You have been logged out successfully.'
        )

    return redirect('products:list')


def password_reset_view(request):

    return render(
        request,
        'accounts/password_reset.html'
    )