from django.test import TestCase
from django.urls import reverse

from .models import Category, Product


class CategoryURLTests(TestCase):

    def test_category_get_absolute_url_points_to_filtered_product_list(self):
        category = Category.objects.create(
            name='Electronics',
            slug='electronics',
            description='Tech gadgets and accessories',
        )

        self.assertEqual(
            category.get_absolute_url(),
            f"{reverse('products:list')}?category={category.pk}"
        )

    def test_category_filter_on_product_list_returns_200(self):
        category = Category.objects.create(
            name='Electronics',
            slug='electronics',
            description='Tech gadgets and accessories',
        )
        Product.objects.create(
            category=category,
            name='Phone',
            slug='phone',
            description='Test phone',
            price='199.99',
            stock=5,
            image='products/test.jpg',
            brand='BrandX',
            sku='SKU-001',
        )

        response = self.client.get(
            reverse('products:list'),
            {'category': category.pk}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Phone')


class ProductDetailTests(TestCase):

    def setUp(self):
        self.category = Category.objects.create(
            name='Electronics',
            slug='electronics',
            description='Tech gadgets'
        )
        self.in_stock_product = Product.objects.create(
            category=self.category,
            name='Smartphone Alpha',
            slug='smartphone-alpha',
            description='A premium smartphone.',
            price='999.99',
            discount_price='899.99',
            stock=10,
            image='products/phone.jpg',
            brand='AlphaBrand',
            sku='SKU-PHONE-ALPHA'
        )
        self.out_of_stock_product = Product.objects.create(
            category=self.category,
            name='Old Phone',
            slug='old-phone',
            description='An outdated phone.',
            price='99.99',
            stock=0,
            image='',
            brand='LegacyBrand',
            sku='SKU-OLD-PHONE'
        )
        self.no_desc_product = Product.objects.create(
            category=self.category,
            name='No Description Phone',
            slug='no-description-phone',
            description='',
            price='49.99',
            stock=5,
            image='',
            brand='BrandY',
            sku='SKU-NO-DESC'
        )

    def test_product_detail_page_fields(self):
        # Test in-stock product detail page
        url = reverse('products:detail', kwargs={'slug': self.in_stock_product.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Verify fields are displayed
        self.assertContains(response, 'Smartphone Alpha')
        self.assertContains(response, 'Electronics')
        self.assertContains(response, 'AlphaBrand')
        self.assertNotContains(response, 'SKU-PHONE-ALPHA')
        self.assertNotContains(response, 'SKU:')
        self.assertContains(response, 'Final Price:')
        self.assertContains(response, 'Rs. 899.99') # final price and discount price
        self.assertContains(response, 'Price:')
        self.assertContains(response, 'Rs. 999.99') # original price
        self.assertContains(response, 'Discount Price:')
        self.assertContains(response, 'Stock: 10')
        self.assertContains(response, 'A premium smartphone.')
        self.assertContains(response, '/media/products/phone.jpg')
        # Since not authenticated, should display login link
        self.assertContains(response, 'Login to Add to Cart')

    def test_out_of_stock_product_detail_page(self):
        # Test out-of-stock product detail page
        url = reverse('products:detail', kwargs={'slug': self.out_of_stock_product.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Verify fields and fallback image
        self.assertContains(response, 'Old Phone')
        self.assertContains(response, 'No Image Available')
        self.assertContains(response, 'Out of Stock')
        self.assertNotContains(response, 'Stock: 0')
        self.assertNotContains(response, 'SKU-OLD-PHONE')
        # Out of stock button should be disabled
        self.assertContains(response, 'disabled')
        # There's no discount, so "Discount Price:" should not be shown
        self.assertNotContains(response, 'Discount Price:')

    def test_no_description_product_detail_page(self):
        # Test product detail page when description is empty
        url = reverse('products:detail', kwargs={'slug': self.no_desc_product.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Description header should not be present
        self.assertNotContains(response, 'Product Description')


