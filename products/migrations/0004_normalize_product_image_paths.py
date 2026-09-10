from pathlib import Path
from urllib.parse import unquote, urlparse

from django.db import migrations


def normalize_product_image_paths(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    updates = []

    for product in Product.objects.exclude(image='').exclude(image__isnull=True).only('id', 'image'):
        image_name = str(product.image)
        parsed_path = urlparse(image_name).path if '://' in image_name else image_name
        filename = Path(unquote(parsed_path)).name
        if not filename:
            continue

        normalized_name = f'products/{filename}'
        if image_name != normalized_name:
            product.image = normalized_name
            updates.append(product)

    if updates:
        Product.objects.bulk_update(updates, ['image'])


def restore_product_image_paths(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('products', '0003_alter_product_slug'),
    ]

    operations = [
        migrations.RunPython(normalize_product_image_paths, restore_product_image_paths),
    ]