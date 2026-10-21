from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from products.models import Product


class Command(BaseCommand):
    help = (
        'Seed the product catalogue from the bundled CSV when the catalogue '
        'is empty. Safe to run on every deploy: it does nothing once active '
        'products already exist.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv',
            type=Path,
            default=Path('pc-components.csv'),
            help='Path to the catalogue CSV file.',
        )
        parser.add_argument(
            '--images-dir',
            type=Path,
            default=Path('static/products'),
            help='Directory containing the catalogue images.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Import even when the catalogue already has active products.',
        )
        parser.add_argument(
            '--default-stock',
            type=int,
            default=100,
            help='Stock for imported rows without a stock column or value.',
        )

    def handle(self, *args, **options):
        csv_path = options['csv'].expanduser()
        images_dir = options['images_dir'].expanduser()

        if not csv_path.is_file():
            raise CommandError(f'Catalogue CSV not found: {csv_path}')

        if not images_dir.is_dir():
            raise CommandError(f'Catalogue images directory not found: {images_dir}')

        if not options['force'] and Product.objects.filter(is_active=True).exists():
            self.stdout.write(
                'Catalogue already has active products; skipping import.'
            )
            return

        call_command(
            'import_pc_components',
            csv_path,
            images_dir=images_dir,
            default_stock=options['default_stock'],
            stdout=self.stdout,
        )
