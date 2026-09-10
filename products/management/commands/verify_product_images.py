from pathlib import Path
from urllib.parse import unquote, urlparse

from django.contrib.staticfiles import finders
from django.core.management.base import BaseCommand
from products.models import Product

class Command(BaseCommand):
    help = 'Verify product images in the database and filesystem.'

    def handle(self, *args, **options):
        products = Product.objects.all()
        total_products = products.count()
        
        with_images = 0
        missing_images = 0
        broken_images = 0
        
        missing_details = []
        broken_details = []
        
        for product in products:
            if not product.image or not product.image.name:
                missing_images += 1
                missing_details.append(product)
            else:
                image_name = str(product.image.name)
                image_path = urlparse(image_name).path if '://' in image_name else image_name
                filename = Path(unquote(image_path)).name
                static_path = f'products/{filename}' if filename else ''
                if static_path and finders.find(static_path):
                    with_images += 1
                else:
                    broken_images += 1
                    broken_details.append(product)
                    
        self.stdout.write(self.style.SUCCESS(f"Products: {total_products}"))
        self.stdout.write(self.style.SUCCESS(f"With images: {with_images}"))
        self.stdout.write(self.style.WARNING(f"Missing images: {missing_images}"))
        self.stdout.write(self.style.ERROR(f"Broken image files: {broken_images}"))
        
        if missing_images > 0 or broken_images > 0:
            self.stdout.write("\n--- Details ---")
            
        for product in missing_details:
            self.stdout.write(self.style.WARNING(
                f"Missing Image - Name: {product.name}, SKU: {product.sku}, Image Field: Empty, Expected file: N/A"
            ))
            
        for product in broken_details:
            self.stdout.write(self.style.ERROR(
                f"Broken Image - Name: {product.name}, SKU: {product.sku}, Image Field: {product.image.name}, Expected static file: products/{Path(unquote(urlparse(str(product.image.name)).path if '://' in str(product.image.name) else str(product.image.name))).name}"
            ))
