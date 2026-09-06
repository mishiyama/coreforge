import csv
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from products.image_matching import image_inventory_row, inventory_images


class Command(BaseCommand):
    help = 'Inventory existing product images without changing the database.'

    def add_arguments(self, parser):
        parser.add_argument('--output', default='product-image-inventory.json')
        parser.add_argument('--format', choices=('json', 'csv'), default='json')

    def handle(self, *args, **options):
        image_dir = Path(settings.MEDIA_ROOT) / 'products'
        candidates = inventory_images(image_dir) if image_dir.exists() else []
        rows = [image_inventory_row(candidate) for candidate in candidates]
        output = Path(options['output'])
        if options['format'] == 'json':
            output.write_text(json.dumps(rows, indent=2), encoding='utf-8')
        else:
            with output.open('w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=rows[0].keys() if rows else [
                    'filename', 'extension', 'file_size', 'width', 'height',
                    'normalized_filename', 'possible_product_keywords',
                ])
                writer.writeheader()
                writer.writerows(rows)
        self.stdout.write(self.style.SUCCESS(
            f'Inventoried {len(rows)} images: {output}'
        ))
