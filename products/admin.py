from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'slug',
        'is_active',
        'created_at',
    )

    list_filter = (
        'is_active',
    )

    search_fields = (
        'name',
    )

    prepopulated_fields = {
        'slug': ('name',)
    }


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):

    list_display = (
        'name',
        'category',
        'brand',
        'price',
        'discount_price',
        'stock',
        'is_active',
    )

    list_filter = (
        'category',
        'is_active',
    )

    search_fields = (
        'name',
        'brand',
        'description',
    )

    prepopulated_fields = {
        'slug': ('name',)
    }

    list_editable = (
        'price',
        'discount_price',
        'stock',
        'is_active',
    )