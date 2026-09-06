from .models import Category


def navbar_categories(request):
    return {
        'nav_categories': Category.objects.filter(
            is_active=True
        )
    }