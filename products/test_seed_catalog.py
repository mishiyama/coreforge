from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from products.models import Category, Product


class SeedCatalogTests(TestCase):

    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.csv_path = self.root / 'components.csv'
        self.images_dir = self.root / 'products'
        self.images_dir.mkdir(parents=True)
        (self.images_dir / 'gpu.jpg').write_bytes(b'not-a-real-image')

        self.csv_path.write_text(
            'category,product_name,price_npr,description,image\n'
            'Graphics Cards,Test GPU,100.00,A test graphics card,gpu.jpg\n',
            encoding='utf-8',
        )

        self.media_root = self.root / 'media'
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)

    def run_seed(self, *arguments):
        stdout = StringIO()
        call_command(
            'seed_catalog',
            '--csv',
            str(self.csv_path),
            '--images-dir',
            str(self.images_dir),
            *arguments,
            stdout=stdout,
            stderr=StringIO(),
        )
        return stdout.getvalue()

    def test_seeds_catalogue_when_empty(self):
        output = self.run_seed()

        self.assertIn('1 created', output)
        self.assertEqual(Product.objects.filter(is_active=True).count(), 1)
        self.assertEqual(Category.objects.filter(is_active=True).count(), 1)

    def test_skips_when_catalogue_already_populated(self):
        self.run_seed()
        output = self.run_seed()

        self.assertIn('skipping import', output)
        self.assertEqual(Product.objects.filter(is_active=True).count(), 1)

    def test_force_reimports_catalogue(self):
        self.run_seed()
        output = self.run_seed('--force')

        self.assertNotIn('skipping import', output)
        self.assertEqual(Product.objects.filter(is_active=True).count(), 1)

    def test_missing_csv_raises_command_error(self):
        with self.assertRaisesMessage(CommandError, 'Catalogue CSV not found'):
            call_command(
                'seed_catalog',
                '--csv',
                str(self.root / 'missing.csv'),
                '--images-dir',
                str(self.images_dir),
                stdout=StringIO(),
                stderr=StringIO(),
            )

    def test_missing_images_directory_raises_command_error(self):
        with self.assertRaisesMessage(
            CommandError,
            'Catalogue images directory not found',
        ):
            call_command(
                'seed_catalog',
                '--csv',
                str(self.csv_path),
                '--images-dir',
                str(self.root / 'missing'),
                stdout=StringIO(),
                stderr=StringIO(),
            )
