import csv
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from orders.models import Order, OrderItem
from products.models import Category, Product


class ImportPCComponentsTests(TestCase):
    required_columns = ['category', 'product_name', 'price_npr', 'description']

    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.csv_path = self.root / 'components.csv'
        self.media_root = self.root / 'media'
        self.images_dir = self.media_root / 'products'
        self.images_dir.mkdir(parents=True)
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)

    def write_csv(self, fieldnames, rows):
        with self.csv_path.open('w', encoding='utf-8', newline='') as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def run_import(self, *arguments):
        stdout = StringIO()
        call_command(
            'import_pc_components',
            str(self.csv_path),
            '--images-dir',
            str(self.images_dir),
            *arguments,
            stdout=stdout,
            stderr=StringIO(),
        )
        return stdout.getvalue()

    def test_required_schema_is_validated(self):
        self.write_csv(
            ['category', 'product_name', 'description'],
            [{
                'category': 'Storage',
                'product_name': 'SSD',
                'description': 'A solid-state drive.',
            }],
        )

        with self.assertRaisesMessage(CommandError, 'missing required columns: price_npr'):
            self.run_import()

        self.assertEqual(Product.objects.count(), 0)

    def test_unexpected_csv_columns_are_rejected(self):
        self.write_csv(
            self.required_columns + ['sku'],
            [{
                'category': 'Storage',
                'product_name': 'SSD',
                'price_npr': '1000',
                'description': 'A solid-state drive.',
                'sku': 'not-allowed',
            }],
        )

        with self.assertRaisesMessage(CommandError, 'unsupported columns: sku'):
            self.run_import()

    def test_import_creates_category_and_is_idempotent(self):
        self.write_csv(
            self.required_columns,
            [{
                'category': ' Storage ',
                'product_name': 'Samsung 870 EVO 1TB SSD',
                'price_npr': 'Rs. 12,499.50',
                'description': 'A fast NVMe solid-state drive.',
            }],
        )

        self.run_import('--default-stock', '7')
        product = Product.objects.get()
        category = Category.objects.get()
        sku = product.sku
        slug = product.slug

        self.assertEqual(category.name, 'Storage')
        self.assertEqual(category.slug, 'storage')
        self.assertEqual(category.description, 'PC components in Storage.')
        self.assertTrue(category.is_active)
        self.assertEqual(product.name, 'Samsung 870 EVO 1TB SSD')
        self.assertEqual(product.price, Decimal('12499.50'))
        self.assertEqual(product.stock, 7)
        self.assertTrue(product.is_active)
        self.assertEqual(product.image.name, '')
        self.assertTrue(sku.startswith('PC-'))
        self.assertLessEqual(len(sku), 50)

        product.stock = 3
        product.discount_price = Decimal('11999.50')
        product.save(update_fields=['stock', 'discount_price'])
        output = self.run_import()
        product.refresh_from_db()

        self.assertEqual(product.sku, sku)
        self.assertEqual(product.slug, slug)
        self.assertEqual(product.stock, 3)
        self.assertEqual(product.discount_price, Decimal('11999.50'))
        self.assertIn('0 created, 0 updated, 1 unchanged', output)
        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(Product.objects.count(), 1)

    def test_colliding_product_names_get_stable_unique_slugs(self):
        self.write_csv(
            self.required_columns,
            [
                {
                    'category': 'Storage',
                    'product_name': 'NVMe Drive',
                    'price_npr': '4,000',
                    'description': 'A storage drive.',
                },
                {
                    'category': 'External Storage',
                    'product_name': 'NVMe Drive',
                    'price_npr': '5,000',
                    'description': 'An external drive.',
                },
            ],
        )

        self.run_import()
        products = list(Product.objects.order_by('category__name'))
        self.assertEqual(len({product.slug for product in products}), 2)
        self.assertEqual(len({product.sku for product in products}), 2)
        first_slugs = {product.sku: product.slug for product in products}
        output = self.run_import()

        self.assertIn('0 created, 0 updated, 2 unchanged', output)
        for product in products:
            product.refresh_from_db()
            self.assertEqual(product.slug, first_slugs[product.sku])

    def test_optional_columns_and_image_filename_matching(self):
        (self.images_dir / 'USB C Cable.jpeg').write_bytes(b'image')
        (self.images_dir / 'wifi-adapter.png').write_bytes(b'image')
        (self.images_dir / 'HDMI Cable.jpg').write_bytes(b'image')
        self.write_csv(
            self.required_columns + ['brand', 'stock', 'image'],
            [
                {
                    'category': 'Accessories',
                    'product_name': 'USB C Cable',
                    'price_npr': '1,250',
                    'description': 'A braided cable.',
                    'brand': 'Acme',
                    'stock': '4',
                    'image': '',
                },
                {
                    'category': 'Networking',
                    'product_name': 'WiFi Adapter',
                    'price_npr': 'NPR 2,500.00',
                    'description': 'A wireless adapter.',
                    'brand': '',
                    'stock': '',
                    'image': '',
                },
                {
                    'category': 'Accessories',
                    'product_name': 'HDMI Cable',
                    'price_npr': 'Rs 900',
                    'description': 'An HDMI cable.',
                    'brand': '',
                    'stock': '',
                    'image': 'products/HDMI_Cable.jpg',
                },
            ],
        )

        output = self.run_import('--default-stock', '9')
        usb = Product.objects.get(name='USB C Cable')
        wifi = Product.objects.get(name='WiFi Adapter')
        hdmi = Product.objects.get(name='HDMI Cable')

        self.assertEqual(usb.image.name, 'products/USB C Cable.jpeg')
        self.assertEqual(wifi.image.name, 'products/wifi-adapter.png')
        self.assertEqual(hdmi.image.name, 'products/HDMI Cable.jpg')
        self.assertEqual(usb.brand, 'Acme')
        self.assertEqual(usb.stock, 4)
        self.assertEqual(wifi.stock, 9)
        self.assertEqual(wifi.brand, '')
        self.assertIn('3 matched, 0 missing', output)

    def test_missing_images_do_not_block_or_clear_products(self):
        self.write_csv(
            self.required_columns,
            [{
                'category': 'Storage',
                'product_name': 'Unphotographed SSD',
                'price_npr': '₨ 3,000',
                'description': 'A drive without a local image.',
            }],
        )

        output = self.run_import()
        product = Product.objects.get()

        self.assertEqual(product.image.name, '')
        self.assertTrue(product.is_active)
        self.assertIn('Images: 0 matched, 1 missing', output)

        product.image.name = 'products/user-selected.jpg'
        product.save(update_fields=['image'])
        self.run_import()
        product.refresh_from_db()
        self.assertEqual(product.image.name, 'products/user-selected.jpg')

    def test_dry_run_reports_without_writing(self):
        old_category = Category.objects.create(
            name='Legacy',
            slug='legacy',
            description='Old products.',
        )
        old_product = Product.objects.create(
            category=old_category,
            name='Legacy RAM',
            slug='legacy-ram',
            description='Old memory.',
            price=Decimal('100'),
            image='products/legacy.jpg',
        )
        self.write_csv(
            self.required_columns,
            [{
                'category': 'Memory',
                'product_name': 'DDR5 RAM',
                'price_npr': '7,500',
                'description': 'A memory module.',
            }],
        )

        output = self.run_import('--dry-run', '--replace')

        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(Product.objects.count(), 1)
        old_product.refresh_from_db()
        self.assertTrue(old_product.is_active)
        self.assertIn('1 would be created', output)
        self.assertIn(
            'Replacement would deactivate: 1 products, 1 categories',
            output,
        )

    def test_replace_hides_old_products_without_deleting_order_history(self):
        old_category = Category.objects.create(
            name='Legacy',
            slug='legacy',
            description='Old products.',
        )
        old_product = Product.objects.create(
            category=old_category,
            name='Legacy Board',
            slug='legacy-board',
            description='An old board.',
            price=Decimal('500'),
            stock=2,
            image='products/legacy.jpg',
            sku='LEGACY-1',
        )
        user = get_user_model().objects.create_user(username='buyer')
        order = Order.objects.create(
            user=user,
            order_number='ORDER-1',
            full_name='Buyer',
            email='buyer@example.com',
            phone='9800000000',
            address='Kathmandu',
            city='Kathmandu',
            province='Bagmati',
            subtotal=Decimal('500'),
            total=Decimal('500'),
        )
        OrderItem.objects.create(
            order=order,
            product=old_product,
            product_name=old_product.name,
            product_price=old_product.price,
            quantity=1,
            subtotal=old_product.price,
        )
        self.write_csv(
            self.required_columns,
            [{
                'category': 'New Parts',
                'product_name': 'Current Board',
                'price_npr': '1,500',
                'description': 'A current board.',
            }],
        )

        output = self.run_import('--replace')
        old_product.refresh_from_db()
        old_category.refresh_from_db()
        current = Product.objects.get(name='Current Board')

        self.assertFalse(old_product.is_active)
        self.assertFalse(old_category.is_active)
        self.assertTrue(current.is_active)
        self.assertTrue(Product.objects.filter(pk=old_product.pk).exists())
        self.assertTrue(OrderItem.objects.filter(product=old_product).exists())
        self.assertIn('1 products and 1 categories deactivated', output)
