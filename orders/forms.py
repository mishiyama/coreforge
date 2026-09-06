from django import forms

from .models import Order


class CheckoutForm(forms.ModelForm):

    class Meta:

        model = Order

        fields = [
            'full_name',
            'email',
            'phone',
            'address',
            'city',
            'province',
            'postal_code',
            'payment_method',
            'notes',
        ]

        widgets = {

            'full_name': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Full Name',
                }
            ),

            'email': forms.EmailInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Email Address',
                }
            ),

            'phone': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Phone Number',
                }
            ),

            'address': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Delivery Address',
                    'rows': 3,
                }
            ),

            'city': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'City',
                }
            ),

            'province': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Province',
                }
            ),

            'postal_code': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Postal Code',
                }
            ),

            'payment_method': forms.Select(
                attrs={
                    'class': 'form-control',
                }
            ),

            'notes': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Additional notes (optional)',
                    'rows': 3,
                }
            ),
        }