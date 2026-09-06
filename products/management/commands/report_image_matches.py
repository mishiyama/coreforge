import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from products.image_matching import inventory_images, match_image


class Command(BaseCommand):
    help = 'Report conservative matches between CSV products and local images.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file')
        parser.add_argument('--output', default=None)

    def handle(self, *args, **options):
        csv_file = Path(options['csv_file'])
        image_dir = Path(settings.MEDIA_ROOT) / 'products'
        candidates = inventory_images(image_dir)
        rows = []
        with csv_file.open('r', encoding='utf-8-sig', newline='') as file:
            for row in csv.DictReader(file):
                match = match_image(row.get('name', ''), row.get('brand', ''),
                                    row.get('image', ''), candidates)
                filename = match.candidate.path.name if match.candidate else ''
                alternatives = ', '.join(item.path.name for item in match.alternatives)
                rows.append((row.get('name', ''), filename, match.status,
                             match.method, match.score, alternatives))
                target = filename or (f'candidates: {alternatives}' if alternatives else 'NO RELIABLE MATCH')
                self.stdout.write(f'{row.get("name", "")} -> {target} [{match.status}; {match.method}]')
        if options['output']:
            output = Path(options['output'])
            with output.open('w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(['name', 'filename', 'status', 'method', 'score', 'alternatives'])
                writer.writerows(rows)
            self.stdout.write(f'Report written: {output}')
        for status in ('MATCHED', 'AMBIGUOUS', 'UNMATCHED'):
            self.stdout.write(f'{status}: {sum(row[2] == status for row in rows)}')
