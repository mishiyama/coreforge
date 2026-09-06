from django.shortcuts import get_object_or_404, render
from django.db.models import Case, When, F, DecimalField

from .models import Category
from .models import Product


def category_list(request):

    categories = Category.objects.filter(
        is_active=True
    )

    return render(
        request,
        'products/category_list.html',
        {'categories': categories}
    )


def category_detail(request, slug):

    category = get_object_or_404(
        Category,
        slug=slug,
        is_active=True
    )
    products = Product.objects.filter(
        category=category,
        is_active=True
    ).select_related('category')

    return render(
        request,
        'products/category_detail.html',
        {
            'category': category,
            'products': products,
        }
    )


def product_list(request):

    products = (
        Product.objects
        .select_related('category')
        .filter(is_active=True)
        .annotate(
            effective_price=Case(
                When(
                    discount_price__isnull=False,
                    then=F('discount_price')
                ),
                default=F('price'),
                output_field=DecimalField(
                    max_digits=10,
                    decimal_places=2
                )
            )
        )
    )

    # ---------------------------------------------------------
    # Search
    # ---------------------------------------------------------

    search = request.GET.get('search', '').strip()

    if search:
        products = products.filter(
            name__icontains=search
        )

    # ---------------------------------------------------------
    # Category
    # ---------------------------------------------------------

    category = request.GET.get('category', '').strip()

    if category:
        products = products.filter(
            category_id=category
        )

    # ---------------------------------------------------------
    # Brand
    # ---------------------------------------------------------

    brand = request.GET.get('brand', '').strip()

    if brand:
        products = products.filter(
            brand__iexact=brand
        )

    # ---------------------------------------------------------
    # Minimum price
    # ---------------------------------------------------------

    min_price = request.GET.get('min_price', '').strip()

    if min_price:
        try:
            products = products.filter(
                effective_price__gte=min_price
            )
        except (ValueError, TypeError):
            pass

    # ---------------------------------------------------------
    # Maximum price
    # ---------------------------------------------------------

    max_price = request.GET.get('max_price', '').strip()

    if max_price:
        try:
            products = products.filter(
                effective_price__lte=max_price
            )
        except (ValueError, TypeError):
            pass

    # ---------------------------------------------------------
    # Sorting
    # ---------------------------------------------------------

    sort = request.GET.get('sort', '').strip()

    if sort == 'price_low':

        products = products.order_by(
            'effective_price'
        )

    elif sort == 'price_high':

        products = products.order_by(
            '-effective_price'
        )

    elif sort == 'name':

        products = products.order_by(
            'name'
        )

    elif sort == 'newest':

        products = products.order_by(
            '-id'
        )

    else:

        products = products.order_by(
            'id'
        )

    # ---------------------------------------------------------
    # Filter options
    # ---------------------------------------------------------

    categories = (
        Product.objects
        .filter(is_active=True)
        .values(
            'category_id',
            'category__name'
        )
        .distinct()
        .order_by('category__name')
    )

    brands = (
        Product.objects
        .filter(is_active=True)
        .values_list(
            'brand',
            flat=True
        )
        .distinct()
        .order_by('brand')
    )

    # ---------------------------------------------------------
    # Context
    # ---------------------------------------------------------

    context = {
        'products': products,
        'categories': categories,
        'brands': brands,

        'search': search,
        'selected_category': category,
        'selected_brand': brand,
        'min_price': min_price,
        'max_price': max_price,
        'selected_sort': sort,
    }

    return render(
        request,
        'products/product_list.html',
        context
    )


def product_detail(request, slug):

    product = get_object_or_404(
        Product,
        slug=slug,
        is_active=True
    )

    context = {
        'product': product,
    }

    return render(
        request,
        'products/product_detail.html',
        context
    )