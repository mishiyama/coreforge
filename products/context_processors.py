from .models import Category


def navbar_categories(request):
    """
    Provide active categories globally for the NepCart navbar.
    """

    return {
        'navbar_categories': Category.objects.filter(
            is_active=True
        ).order_by('name')
    }