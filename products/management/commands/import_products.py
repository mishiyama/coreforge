import sys
import csv
import os
import re
import urllib.request
import urllib.error

from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from products.models import Category, Product


csv.field_size_limit(sys.maxsize)


class Command(BaseCommand):
    help = 'Import NepCart products from an Amazon-style CSV file.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str)
        parser.add_argument('--no-images', action='store_true', help='Do not load product images.')
        parser.add_argument('--dry-run', action='store_true', help='Report mappings without saving.')
        parser.add_argument('--limit', type=int, default=None, help='Limit the number of products imported.')

    def handle(self, *args, **options):
        csv_file_path = Path(options['csv_file'])
        no_images = options['no_images']
        dry_run = options['dry_run']
        limit = options['limit']

        if not csv_file_path.exists():
            self.stdout.write(self.style.ERROR(f'File not found: {csv_file_path}'))
            return

        media_products_dir = Path(settings.MEDIA_ROOT) / 'products'
        media_products_dir.mkdir(parents=True, exist_ok=True)

        created_count = 0
        updated_count = 0
        skipped_count = 0
        local_match_count = 0
        download_count = 0
        unavailable_count = 0

        required_columns = [
            'title', 'categories', 'asin', 'final_price',
            'initial_price', 'availability', 'is_available', 'image_url'
        ]

        with csv_file_path.open('r', encoding='utf-8-sig', newline='') as file:
            reader = csv.DictReader(file)
            fieldnames = reader.fieldnames or []

            missing_columns = [col for col in required_columns if col not in fieldnames]
            if missing_columns:
                self.stdout.write(self.style.ERROR('Missing required CSV columns: ' + ', '.join(missing_columns)))
                return

            if dry_run:
                self.stdout.write(self.style.NOTICE("--- DRY RUN MODE ---"))

            for row_number, row in enumerate(reader, start=2):
                if limit and (created_count + updated_count + skipped_count) >= limit:
                    break

                title = (row.get('title') or '').strip()
                categories_str = (row.get('categories') or '').strip()
                asin = (row.get('asin') or '').strip()
                final_price_str = row.get('final_price')
                initial_price_str = row.get('initial_price')
                availability = (row.get('availability') or '').strip().lower()
                is_available_str = (row.get('is_available') or '').strip().lower()
                image_url = (row.get('image_url') or '').strip()

                if not title or not asin:
                    self.stdout.write(self.style.WARNING(f'Row {row_number}: missing title or ASIN. Skipping.'))
                    skipped_count += 1
                    continue

                sku = f"AMZ-{asin}"
                if len(sku) > 50:
                    sku = sku[:50]

                # Brand extraction
                brand = ""
                first_word = title.split()[0] if title.split() else ""
                if first_word.isalpha() and len(first_word) > 2:
                    brand = first_word

                # Category extraction
                category_name = self.extract_category(categories_str)
                if not category_name:
                    self.stdout.write(self.style.WARNING(f'Skipping "{title}": missing category.'))
                    skipped_count += 1
                    continue

                # Prices
                final_price = self.parse_price(final_price_str)
                initial_price = self.parse_price(initial_price_str)

                if final_price is None or final_price <= 0:
                    self.stdout.write(self.style.WARNING(f'Skipping "{title}": invalid final_price.'))
                    skipped_count += 1
                    continue

                price = final_price
                discount_price = None

                if initial_price is not None and initial_price > final_price:
                    price = initial_price
                    discount_price = final_price

                # Stock
                stock = 100
                if is_available_str in ('false', '0', 'no') or availability in (
                    'out of stock', 'unavailable', 'currently unavailable', 'not available', 'sold out'
                ):
                    stock = 0

                # Description
                description = f"{title}"
                if brand:
                    description += f" by {brand}."
                else:
                    description += "."
                description += f" Category: {category_name}."

                # Slug
                slug = self.make_unique_slug(title, sku)

                if dry_run:
                    self.stdout.write(f"\nRow {row_number}")
                    self.stdout.write(f"Title: {title}")
                    self.stdout.write(f"ASIN: {asin}")
                    self.stdout.write(f"SKU: {sku}")
                    self.stdout.write(f"Category: {category_name}")
                    self.stdout.write(f"Price: {final_price}")
                    
                    image_status, image_file_or_url = self.resolve_image(asin, image_url, media_products_dir, dry_run=True, no_images=no_images)
                    if image_status == "LOCAL MATCH":
                        self.stdout.write("Image: LOCAL MATCH")
                        self.stdout.write(f"Image file: {image_file_or_url}")
                        local_match_count += 1
                    elif image_status == "DOWNLOAD":
                        self.stdout.write("Image: DOWNLOAD")
                        self.stdout.write(f"URL: {image_file_or_url}")
                        download_count += 1
                    else:
                        self.stdout.write("Image: UNAVAILABLE")
                        unavailable_count += 1
                        
                    # Estimate create vs update for dry run
                    if Product.objects.filter(sku=sku).exists():
                        updated_count += 1
                    else:
                        created_count += 1
                        
                    continue

                # Actual Import
                category = self.get_or_create_category(category_name)
                
                product, created = Product.objects.update_or_create(
                    sku=sku,
                    defaults={
                        'category': category,
                        'name': title[:200],
                        'slug': slug,
                        'description': description,
                        'price': price,
                        'discount_price': discount_price,
                        'stock': stock,
                        'brand': brand[:100],
                        'is_active': stock > 0,
                    }
                )

                if not no_images:
                    image_status, image_info = self.resolve_image(asin, image_url, media_products_dir, dry_run=False, no_images=no_images)
                    
                    if image_status == "LOCAL MATCH":
                        if not product.image or Path(product.image.path).name != image_info:
                            product.image.name = f"products/{image_info}"
                            product.save(update_fields=['image'])
                        local_match_count += 1
                    elif image_status == "DOWNLOAD":
                        if self.download_and_attach_image(product, image_url):
                            download_count += 1
                        else:
                            unavailable_count += 1
                    else:
                        unavailable_count += 1

                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f'Created: {product.name}'))
                else:
                    updated_count += 1
                    self.stdout.write(self.style.WARNING(f'Updated: {product.name}'))

        # Summary
        self.stdout.write('\n--- Import Summary ---')
        if dry_run:
            self.stdout.write(self.style.SUCCESS(f'Would create: {created_count}'))
            self.stdout.write(self.style.SUCCESS(f'Would update: {updated_count}'))
            self.stdout.write(self.style.WARNING(f'Would skip: {skipped_count}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Created: {created_count}'))
            self.stdout.write(self.style.SUCCESS(f'Updated: {updated_count}'))
            self.stdout.write(self.style.WARNING(f'Skipped: {skipped_count}'))
            
        if not no_images:
            self.stdout.write(self.style.SUCCESS(f'Local image matches: {local_match_count}'))
            self.stdout.write(self.style.SUCCESS(f'Images to download: {download_count}'))
            self.stdout.write(self.style.WARNING(f'Images unavailable: {unavailable_count}'))


    def extract_category(self, categories_str):
        if not categories_str:
            return ""
            
        # Clean up JSON-like array strings if present
        cleaned = re.sub(r'^[\[\"\'\s]+|[\]\"\'\s]+$', '', categories_str)
        cleaned = cleaned.replace('","', ',').replace("','", ',')
        
        # Handle formats like "A > B > C", "A | B | C", or "A, B, C"
        delimiters = ['>', '|', ',']
        for delim in delimiters:
            if delim in cleaned:
                parts = [p.strip(' "\'[]') for p in cleaned.split(delim) if p.strip(' "\'[]')]
                if parts:
                    return parts[-1]
                    
        return cleaned.strip(' "\'[]')

    def get_or_create_category(self, name):
        category = Category.objects.filter(name__iexact=name).first()
        if category:
            return category
        
        category = Category.objects.create(
            name=name[:100],
            slug=self.make_category_slug(name),
            description=f'Products in {name}.',
            is_active=True
        )
        return category

    def make_category_slug(self, name):
        base = self.slugify(name) or 'category'
        slug = base
        counter = 2
        while Category.objects.filter(slug=slug).exists():
            slug = f'{base}-{counter}'
            counter += 1
        return slug

    def parse_price(self, value):
        if value is None:
            return None
        value = str(value).strip()
        if not value:
            return None

        # Handle currency symbols and commas
        value = re.sub(r'[^\d.,-]', '', value)
        if not value:
            return None

        if ',' in value and '.' in value:
            if value.rfind(',') < value.rfind('.'):
                value = value.replace(',', '')
            else:
                value = value.replace('.', '').replace(',', '.')
        elif ',' in value:
            parts = value.split(',')
            if len(parts[-1]) == 2:
                value = ''.join(parts[:-1]) + '.' + parts[-1]
            else:
                value = value.replace(',', '')
        try:
            return Decimal(value)
        except InvalidOperation:
            return None

    def make_unique_slug(self, name, sku):
        base = self.slugify(name) or 'product'
        slug = base[:200]
        
        existing = Product.objects.filter(slug=slug).first()
        if not existing:
            return slug
        if existing.sku == sku:
            return existing.slug
            
        sku_slug = self.slugify(sku)
        slug = f'{base}-{sku_slug}'.lower()[:200]
        
        counter = 2
        original_slug = slug
        while Product.objects.filter(slug=slug).exclude(sku=sku).exists():
            suffix = f'-{counter}'
            slug = original_slug[:200 - len(suffix)] + suffix
            counter += 1
        return slug

    def slugify(self, value):
        value = str(value).lower()
        value = re.sub(r'[^a-z0-9]+', '-', value)
        return value.strip('-')

    def resolve_image(self, asin, image_url, media_products_dir, dry_run=False, no_images=False):
        if no_images:
            return "UNAVAILABLE", None
            
        extensions = ['.jpg', '.jpeg', '.png', '.webp', '.avif']
        
        # Priority 1: Local ASIN image
        for ext in extensions:
            candidate_name = f"amz-{asin.lower()}{ext}"
            if (media_products_dir / candidate_name).is_file():
                return "LOCAL MATCH", candidate_name

        # Priority 2: Exact filename match for image_url
        if image_url:
            parsed = urlparse(image_url)
            filename = os.path.basename(parsed.path)
            if filename:
                # Check case-insensitive
                for file_path in media_products_dir.iterdir():
                    if file_path.is_file() and file_path.name.lower() == filename.lower():
                        return "LOCAL MATCH", file_path.name

        # Priority 3: Download image_url
        if image_url and image_url.startswith(('http://', 'https://')):
            return "DOWNLOAD", image_url

        return "UNAVAILABLE", None

    def download_and_attach_image(self, product, image_url):
        try:
            req = urllib.request.Request(
                image_url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status != 200:
                    return False
                
                content_type = response.headers.get('Content-Type', '')
                if not content_type.startswith('image/'):
                    return False
                
                image_content = response.read()
                
            parsed = urlparse(image_url)
            filename = os.path.basename(parsed.path)
            if not filename:
                filename = f"image_{product.sku}.jpg"
                
            product.image.save(filename, ContentFile(image_content), save=True)
            return True
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Failed to download image from {image_url}: {e}"))
            return False