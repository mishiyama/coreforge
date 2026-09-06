from django import forms
from django.contrib.auth.models import User

from .models import CustomerProfile


class RegisterForm(forms.ModelForm):

    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Enter your password',
                'autocomplete': 'new-password',
            }
        )
    )

    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Confirm your password',
                'autocomplete': 'new-password',
            }
        )
    )

    class Meta:
        model = User

        fields = [
            'username',
            'email',
            'password1',
            'password2',
        ]

        widgets = {
            'username': forms.TextInput(
                attrs={
                    'placeholder': 'Enter your username',
                    'autocomplete': 'username',
                }
            ),

            'email': forms.EmailInput(
                attrs={
                    'placeholder': 'Enter your email address',
                    'autocomplete': 'email',
                }
            ),
        }

    def clean(self):

        cleaned_data = super().clean()

        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        if password1 and password2:

            if password1 != password2:

                raise forms.ValidationError(
                    'Passwords do not match.'
                )

        return cleaned_data

    def save(self, commit=True):

        user = super().save(commit=False)

        user.set_password(
            self.cleaned_data['password1']
        )

        if commit:
            user.save()

        return user


class LoginForm(forms.Form):

    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Enter your username',
                'autocomplete': 'username',
            }
        )
    )

    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Enter your password',
                'autocomplete': 'current-password',
            }
        )
    )

    remember_me = forms.BooleanField(
        required=False,
        label='Remember me',
        widget=forms.CheckboxInput(
            attrs={
                'id': 'remember_me',
            }
        )
    )


class ProfileForm(forms.Form):

    first_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Enter your first name',
            }
        )
    )

    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Enter your last name',
            }
        )
    )

    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(
            attrs={
                'placeholder': 'Enter your email address',
            }
        )
    )

    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Enter your phone number',
            }
        )
    )

    profile_image = forms.ImageField(
        required=False
    )