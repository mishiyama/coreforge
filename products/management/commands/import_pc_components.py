import argparse
import csv
import hashlib
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from products.models import Category, Product


csv.field_size_limit(sys.maxsize)

REQUIRED_COLUMNS = frozenset({
    'category',
    'product_name',
    'price_npr',
    'description',
})
OPTIONAL_COLUMNS = frozenset({'brand', 'stock', 'image'})
SUPPORTED_IMAGE_EXTENSIONS = frozenset({'.avif', '.jpeg', '.jpg', '.png', '.webp'})
BRAND_LABEL = re.compile(r'\bbrand\s*:\s*([^.;|\r\n]{1,100})', re.IGNORECASE)
CURRENCY_PREFIX = re.compile(
    r'^\s*(?:npr|rs\.?|rupees?)\s*[:=]?\s*',
    re.IGNORECASE,
)
CURRENCY_SUFFIX = re.compile(
    r'\s*(?:npr|rs\.?|rupees?)\s*$',
    re.IGNORECASE,
)
CURRENCY_SYMBOLS = re.compile(r'[₨$€£¥]')


@dataclass(frozen=True)
class ComponentRow:
    row_number: int
    category: str
    product_name: str
    price: Decimal
    description: str
    brand: str | None
    stock: int | None
    image: str


@dataclass
class ImportSummary:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    categories_created: int = 0
    categories_reused: int = 0
    images_matched: int = 0
    images_missing: int = 0
    skipped: int = 0
    blank_rows: int = 0
    invalid_rows: int = 0
    duplicate_rows: int = 0
    products_deactivated: int = 0
    categories_deactivated: int = 0
    products_reactivated: int = 0
    categories_reactivated: int = 0


def non_negative_integer(value):
    try:
        integer = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('must be an integer') from exc
    if integer < 0 or integer > 2_147_483_647:
        raise argparse.ArgumentTypeError('must be between 0 and 2147483647')
    return integer


def canonical_text(value):
    normalized = unicodedata.normalize('NFKC', str(value)).casefold()
    return ' '.join(normalized.split())


def stable_digest(category, product_name):
    value = f'pc-components:v1\0{canonical_text(category)}\0{canonical_text(product_name)}'
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def normalize_image_stem(value):
    normalized = unicodedata.normalize('NFKC', str(value)).casefold()
    return re.sub(r'[\W_]+', '', normalized)


def parse_stock(value):
    text = str(value or '').strip()
    if not re.fullmatch(r'\d+', text):
        raise ValueError('stock must be a non-negative integer')
    stock = int(text)
    if stock > 2_147_483_647:
        raise ValueError('stock must be at most 2147483647')
    return stock


def parse_price(value):
    text = unicodedata.normalize('NFKC', str(value or '')).strip()
    text = CURRENCY_PREFIX.sub('', text)
    text = CURRENCY_SUFFIX.sub('', text)
    text = CURRENCY_SYMBOLS.sub('', text)
    text = re.sub(r'/\s*-\s*$', '', text)
    text = text.replace('−', '-').replace('–', '-').replace('—', '-').strip()

    negative = False
    if text.startswith('(') and text.endswith(')'):
        negative = True
        text = text[1:-1].strip()

    if text.count('+') + text.count('-') > 1:
        return None
    if '-' in text:
        negative = not negative
    text = text.replace('+', '').replace('-', '').strip()
    text = re.sub(r'\s+', '', text)

    if not re.fullmatch(r'\d[\d,.]*', text):
        return None

    has_dot = '.' in text
    has_comma = ',' in text
    if has_dot and has_comma:
        decimal_separator = '.' if text.rfind('.') > text.rfind(',') else ','
        separator = ',' if decimal_separator == '.' else '.'
        integer, fraction = text.rsplit(decimal_separator, 1)
        if not integer or not fraction or not fraction.isdigit():
            return None
        if separator in integer:
            groups = integer.split(separator)
            if not all(group.isdigit() for group in groups):
                return None
            if not 1 <= len(groups[0]) <= 3 or any(
                len(group) not in {2, 3} for group in groups[1:]
            ):
                return None
            integer = ''.join(groups)
        elif not integer.isdigit():
            return None
        normalized = f'{integer}.{fraction}'
    elif has_comma:
        groups = text.split(',')
        if len(groups) == 2 and len(groups[1]) == 3 and len(groups[0]) <= 3:
            if not groups[0].isdigit() or not groups[1].isdigit():
                return None
            normalized = ''.join(groups)
        elif len(groups) > 1 and all(group.isdigit() for group in groups):
            if not 1 <= len(groups[0]) <= 3 or any(
                len(group) not in {2, 3} for group in groups[1:]
            ):
                return None
            if len(groups[-1]) == 3:
                normalized = ''.join(groups)
            else:
                normalized = f'{"".join(groups[:-1])}.{groups[-1]}'
        else:
            return None
    elif has_dot:
        integer, fraction = text.rsplit('.', 1)
        if not integer or not fraction or not integer.isdigit() or not fraction.isdigit():
            return None
        normalized = f'{integer}.{fraction}'
    else:
        normalized = text

    try:
        price = Decimal(normalized)
        if negative:
            price = -price
        price = price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None

    if not price.is_finite() or price <= 0 or price >= Decimal('100000000'):
        return None
    return price


class Command(BaseCommand):
    help = 'Import COREFORGE PC component products from a CSV file.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=Path)
        parser.add_argument(
            '--images-dir',
            type=Path,
            default=None,
            help='Directory containing local product images.',
        )
        parser.add_argument(
            '--default-stock',
            type=non_negative_integer,
            default=100,
            help='Stock for imported rows without a stock column or value.',
        )
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Deactivate the existing catalog before importing this CSV.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report import changes without writing to the database.',
        )

    def handle(self, *args, **options):
        csv_path = options['csv_path'].expanduser()
        if not csv_path.exists():
            raise CommandError(f'CSV file not found: {csv_path}')
        if not csv_path.is_file():
            raise CommandError(f'CSV path is not a file: {csv_path}')

        images_dir = self._images_directory(options['images_dir'])
        rows, summary = self._read_rows(csv_path)
        image_index = self._build_image_index(images_dir)
        product_keys = [self._product_key(row) for row in rows]
        existing_products = {
            product.sku: product
            for product in Product.objects.filter(
                sku__in=[f'PC-{key[:46]}' for key in product_keys]
            )
        }
        existing_categories = {}
        for row in rows:
            category_key = canonical_text(row.category)
            if category_key in existing_categories:
                continue
            category = Category.objects.filter(name__iexact=row.category).first()
            if category:
                existing_categories[category_key] = category

        if options['dry_run']:
            if options['replace']:
                summary.products_deactivated = Product.objects.filter(
                    is_active=True
                ).count()
                summary.categories_deactivated = Category.objects.filter(
                    is_active=True
                ).count()
            self._run_import(
                rows,
                summary,
                image_index,
                existing_products,
                existing_categories,
                options['default_stock'],
                options['replace'],
                dry_run=True,
            )
        else:
            with transaction.atomic():
                if options['replace']:
                    summary.products_deactivated = Product.objects.filter(
                        is_active=True
                    ).update(is_active=False)
                    summary.categories_deactivated = Category.objects.filter(
                        is_active=True
                    ).update(is_active=False)
                self._run_import(
                    rows,
                    summary,
                    image_index,
                    existing_products,
                    existing_categories,
                    options['default_stock'],
                    options['replace'],
                    dry_run=False,
                )

        self._report(summary, options['dry_run'], options['replace'])

    def _images_directory(self, supplied_path):
        if supplied_path is not None:
            images_dir = supplied_path.expanduser()
            if not images_dir.exists():
                raise CommandError(f'Images directory not found: {images_dir}')
            if not images_dir.is_dir():
                raise CommandError(f'Images path is not a directory: {images_dir}')
            return images_dir

        images_dir = Path(settings.MEDIA_ROOT) / 'products'
        if images_dir.exists() and not images_dir.is_dir():
            raise CommandError(f'Images path is not a directory: {images_dir}')
        return images_dir

    def _read_rows(self, csv_path):
        rows = []
        summary = ImportSummary()

        try:
            with csv_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
                reader = csv.DictReader(csv_file, strict=True)
                fieldnames = reader.fieldnames
                if not fieldnames:
                    raise CommandError('CSV file must contain a header row.')

                counts = Counter(fieldnames)
                duplicates = sorted(
                    field for field, count in counts.items() if count > 1
                )
                missing = sorted(REQUIRED_COLUMNS - set(fieldnames))
                unexpected = sorted(
                    set(fieldnames) - REQUIRED_COLUMNS - OPTIONAL_COLUMNS
                )
                errors = []
                if duplicates:
                    errors.append(f'duplicate columns: {", ".join(duplicates)}')
                if missing:
                    errors.append(
                        f'missing required columns: {", ".join(missing)}'
                    )
                if unexpected:
                    errors.append(f'unsupported columns: {", ".join(unexpected)}')
                if errors:
                    raise CommandError('Invalid CSV schema: ' + '; '.join(errors))

                for row_number, raw_row in enumerate(reader, start=2):
                    if raw_row.get(None):
                        raise CommandError(
                            f'Row {row_number}: more values than CSV columns.'
                        )

                    if all(
                        not isinstance(value, str) or not value.strip()
                        for value in raw_row.values()
                    ):
                        summary.blank_rows += 1
                        summary.skipped += 1
                        continue

                    try:
                        row = self._parse_row(raw_row, row_number, fieldnames)
                    except ValueError as exc:
                        summary.invalid_rows += 1
                        summary.skipped += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f'Row {row_number}: {exc}; skipped.'
                            )
                        )
                        continue
                    rows.append(row)
        except CommandError:
            raise
        except (OSError, UnicodeError, csv.Error) as exc:
            raise CommandError(f'Unable to read CSV file: {exc}') from exc

        return rows, summary

    def _parse_row(self, raw_row, row_number, fieldnames):
        category = self._required_text(raw_row, 'category', 100)
        product_name = self._required_text(raw_row, 'product_name', 200)
        description = self._required_text(raw_row, 'description')
        price_text = self._required_text(raw_row, 'price_npr')
        price = parse_price(price_text)
        if price is None:
            raise ValueError('price_npr must be a positive amount below 100000000')

        brand = self._optional_text(raw_row, 'brand', 100)
        if not brand:
            brand = self._infer_brand(product_name, description)
        if brand and len(brand) > 100:
            brand = None

        stock = None
        if 'stock' in fieldnames and (raw_row.get('stock') or '').strip():
            stock = parse_stock(raw_row.get('stock'))

        image = self._optional_text(raw_row, 'image')
        return ComponentRow(
            row_number=row_number,
            category=category,
            product_name=product_name,
            price=price,
            description=description,
            brand=brand,
            stock=stock,
            image=image,
        )

    def _required_text(self, raw_row, field, max_length=None):
        value = str(raw_row.get(field) or '').strip()
        if not value:
            raise ValueError(f'{field} is required')
        if '\x00' in value:
            raise ValueError(f'{field} contains an invalid null character')
        if max_length and len(value) > max_length:
            raise ValueError(f'{field} must be at most {max_length} characters')
        return value

    def _optional_text(self, raw_row, field, max_length=None):
        value = str(raw_row.get(field) or '').strip()
        if not value:
            return ''
        if '\x00' in value:
            raise ValueError(f'{field} contains an invalid null character')
        if max_length and len(value) > max_length:
            raise ValueError(f'{field} must be at most {max_length} characters')
        return value

    def _infer_brand(self, product_name, description):
        for value in (product_name, description):
            match = BRAND_LABEL.search(value)
            if match:
                brand = match.group(1).strip(' -_')
                if brand:
                    return brand[:100]
        return None

    def _build_image_index(self, images_dir):
        by_stem = {}
        by_filename = {}
        if not images_dir.exists():
            return by_stem, by_filename

        try:
            paths = sorted(
                images_dir.iterdir(),
                key=lambda path: path.name.casefold(),
            )
        except OSError as exc:
            raise CommandError(f'Unable to read images directory: {exc}') from exc

        for path in paths:
            extension = path.suffix.lower()
            if not path.is_file() or extension not in SUPPORTED_IMAGE_EXTENSIONS:
                continue
            normalized = normalize_image_stem(path.stem)
            by_stem.setdefault(normalized, []).append(path)
            by_filename.setdefault((normalized, extension), []).append(path)
        return by_stem, by_filename

    def _run_import(
        self,
        rows,
        summary,
        image_index,
        existing_products,
        existing_categories,
        default_stock,
        replace,
        dry_run,
    ):
        category_slugs = set()
        product_slugs = set()
        processed_categories = set()
        seen_products = set()

        for row in rows:
            product_key = self._product_key(row)
            if product_key in seen_products:
                summary.duplicate_rows += 1
                summary.skipped += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'Row {row.row_number}: duplicate product; skipped.'
                    )
                )
                continue
            seen_products.add(product_key)

            category = self._get_category(
                row,
                summary,
                existing_categories,
                category_slugs,
                processed_categories,
                replace,
                dry_run,
            )
            self._get_product(
                row,
                product_key,
                category,
                summary,
                image_index,
                existing_products,
                product_slugs,
                default_stock,
                replace,
                dry_run,
            )

    def _get_category(
        self,
        row,
        summary,
        category_map,
        reserved_slugs,
        processed_categories,
        replace,
        dry_run,
    ):
        category_key = canonical_text(row.category)
        if category_key in processed_categories:
            return category_map[category_key]
        processed_categories.add(category_key)

        category = category_map.get(category_key)
        if category is None:
            category = Category.objects.filter(name__iexact=row.category).first()
        if category:
            category_map[category_key] = category
            summary.categories_reused += 1
            was_active = category.is_active
            if replace and not was_active:
                summary.categories_reactivated += 1
            category.is_active = True
            if not dry_run and (replace or not was_active):
                self._save_category(category, row.row_number)
            return category

        digest = stable_digest(row.category, row.category)
        slug = self._resolve_category_slug(row.category, digest, reserved_slugs)
        reserved_slugs.add(slug)
        category = Category(
            name=row.category,
            slug=slug,
            description=f'PC components in {row.category}.',
            is_active=True,
        )
        category_map[category_key] = category
        summary.categories_created += 1
        self._validate_category(category, row.row_number)
        if not dry_run:
            category.save()
        return category

    def _resolve_category_slug(self, name, digest, reserved_slugs):
        for candidate in self._slug_candidates(name, digest, 'category'):
            if candidate in reserved_slugs:
                continue
            if Category.objects.filter(slug=candidate).exists():
                continue
            return candidate
        raise CommandError(f'Unable to generate a unique category slug for {name!r}')

    def _get_product(
        self,
        row,
        product_key,
        category,
        summary,
        image_index,
        product_map,
        reserved_slugs,
        default_stock,
        replace,
        dry_run,
    ):
        sku = f'PC-{product_key[:46]}'
        product = product_map.get(sku)

        if product:
            slug = product.slug
        else:
            slug = self._resolve_product_slug(
                row.product_name,
                product_key,
                reserved_slugs,
            )
            reserved_slugs.add(slug)

        image_path = self._match_image(row, slug, image_index)
        if image_path:
            summary.images_matched += 1
            image_name = f'products/{image_path.name}'
        else:
            summary.images_missing += 1
            image_name = None

        if product:
            was_active = product.is_active
            values = [
                ('category', category),
                ('name', row.product_name),
                ('description', row.description),
                ('price', row.price),
                ('is_active', True),
            ]
            if row.stock is not None:
                values.append(('stock', row.stock))
            if row.brand is not None:
                values.append(('brand', row.brand))
            if image_name is not None:
                values.append(('image', image_name))

            changed_fields = []
            for field, value in values:
                current = self._field_value(product, field)
                if current != value:
                    changed_fields.append(field)
                setattr(product, field, value)

            if replace and not was_active:
                summary.products_reactivated += 1
            self._validate_product(product, row.row_number, dry_run)

            if not dry_run and (changed_fields or replace):
                update_fields = set(changed_fields)
                if replace:
                    update_fields.add('is_active')
                update_fields.add('updated_at')
                product.save(update_fields=list(update_fields))
            if changed_fields:
                summary.updated += 1
            else:
                summary.unchanged += 1
            return product

        product = Product(
            category=category,
            name=row.product_name,
            slug=slug,
            description=row.description,
            price=row.price,
            stock=row.stock if row.stock is not None else default_stock,
            brand=row.brand or '',
            sku=sku,
            is_active=True,
        )
        product.image.name = image_name or ''
        self._validate_product(product, row.row_number, dry_run)
        if not dry_run:
            product.save()
            product_map[sku] = product
        summary.created += 1
        return product

    def _field_value(self, product, field):
        if field == 'category':
            return product.category
        if field == 'image':
            return product.image.name or ''
        return getattr(product, field)

    def _validate_category(self, category, row_number):
        try:
            category.full_clean()
        except ValidationError as exc:
            raise CommandError(
                f'Row {row_number}: invalid category: {"; ".join(exc.messages)}'
            ) from exc

    def _save_category(self, category, row_number):
        self._validate_category(category, row_number)
        category.save(update_fields=['is_active', 'updated_at'])

    def _validate_product(self, product, row_number, dry_run=False):
        try:
            excluded = {'image', 'category'} if dry_run else {'image'}
            product.full_clean(exclude=excluded)
        except ValidationError as exc:
            raise CommandError(
                f'Row {row_number}: invalid product: {"; ".join(exc.messages)}'
            ) from exc

    def _resolve_product_slug(self, name, digest, reserved_slugs):
        for candidate in self._slug_candidates(name, digest, 'product'):
            if candidate in reserved_slugs:
                continue
            if Product.objects.filter(slug=candidate).exists():
                continue
            return candidate
        raise CommandError(f'Unable to generate a unique product slug for {name!r}')

    def _slug_candidates(self, name, digest, fallback):
        base = (slugify(name, allow_unicode=False) or fallback)[:200]
        yield base
        for width in (12, 20, 40, 64):
            suffix = f'-{digest[:width]}'
            prefix = base[:200 - len(suffix)].rstrip('-') or fallback
            yield f'{prefix}{suffix}'

    def _match_image(self, row, slug, image_index):
        by_stem, by_filename = image_index

        if row.image:
            parsed = urlsplit(row.image)
            if parsed.scheme or parsed.netloc:
                return None
            requested = row.image.replace('\\', '/').rsplit('/', 1)[-1].strip()
            requested_path = Path(requested)
            extension = requested_path.suffix.lower()
            if extension not in SUPPORTED_IMAGE_EXTENSIONS:
                return None
            matches = by_filename.get(
                (normalize_image_stem(requested_path.stem), extension),
                [],
            )
        else:
            matches = by_stem.get(normalize_image_stem(row.product_name), [])
            if not matches:
                matches = by_stem.get(normalize_image_stem(slug), [])

        return matches[0] if len(matches) == 1 else None

    def _product_key(self, row):
        return stable_digest(row.category, row.product_name)

    def _report(self, summary, dry_run, replace):
        self.stdout.write('')
        if dry_run:
            self.stdout.write(
                f'Products: {summary.created} would be created, '
                f'{summary.updated} would be updated, '
                f'{summary.unchanged} would be unchanged'
            )
            self.stdout.write(
                f'Categories: {summary.categories_created} would be created, '
                f'{summary.categories_reused} would be reused'
            )
        else:
            self.stdout.write(
                f'Products: {summary.created} created, '
                f'{summary.updated} updated, '
                f'{summary.unchanged} unchanged'
            )
            self.stdout.write(
                f'Categories: {summary.categories_created} created, '
                f'{summary.categories_reused} reused'
            )
        self.stdout.write(
            f'Images: {summary.images_matched} matched, '
            f'{summary.images_missing} missing'
        )
        self.stdout.write(
            f'Skipped: {summary.skipped} '
            f'(blank: {summary.blank_rows}, '
            f'invalid: {summary.invalid_rows}, '
            f'duplicate: {summary.duplicate_rows})'
        )
        if replace:
            if dry_run:
                self.stdout.write(
                    f'Replacement would deactivate: {summary.products_deactivated} products, '
                    f'{summary.categories_deactivated} categories'
                )
                self.stdout.write(
                    f'Replacement would reactivate: {summary.products_reactivated} products, '
                    f'{summary.categories_reactivated} categories'
                )
            else:
                self.stdout.write(
                    f'Replaced: {summary.products_deactivated} products and '
                    f'{summary.categories_deactivated} categories deactivated'
                )
                self.stdout.write(
                    f'Reactivated: {summary.products_reactivated} products and '
                    f'{summary.categories_reactivated} categories'
                )
