import os

from django.core.management.base import BaseCommand
from django.db import transaction

from products.models import Product
from orders.models import OrderItem


class Command(BaseCommand):
    help = (
        "Safely clear the product catalog while preserving "
        "products referenced by existing orders."
    )

    def handle(self, *args, **options):

        products = Product.objects.all()
        total_count = products.count()

        if total_count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "No products found in the database."
                )
            )
            return

        # ---------------------------------------------------------
        # Find products referenced by existing OrderItems.
        #
        # These products MUST NOT be deleted because
        # OrderItem.product uses on_delete=PROTECT.
        # ---------------------------------------------------------

        purchased_product_ids = set(
            OrderItem.objects
            .values_list("product_id", flat=True)
            .distinct()
        )

        purchased_products = products.filter(
            id__in=purchased_product_ids
        )

        unused_products = products.exclude(
            id__in=purchased_product_ids
        )

        purchased_count = purchased_products.count()
        unused_count = unused_products.count()

        # ---------------------------------------------------------
        # Collect image paths ONLY for products that will be
        # permanently deleted.
        # ---------------------------------------------------------

        image_paths = []

        for product in unused_products:

            if product.image:

                try:
                    path = product.image.path

                    if os.path.exists(path):
                        image_paths.append(path)

                except (ValueError, OSError):
                    pass

        # ---------------------------------------------------------
        # Display what is going to happen
        # ---------------------------------------------------------

        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                f"Total products found: {total_count}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Products that can be permanently deleted: "
                f"{unused_count}"
            )
        )

        self.stdout.write(
            self.style.WARNING(
                f"Purchased products that will be preserved: "
                f"{purchased_count}"
            )
        )

        self.stdout.write(
            self.style.WARNING(
                f"Product images to delete: "
                f"{len(image_paths)}"
            )
        )

        # ---------------------------------------------------------
        # Show protected products
        # ---------------------------------------------------------

        if purchased_count > 0:

            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "Purchased products will be preserved for "
                    "historical order records:"
                )
            )

            for product in purchased_products:
                self.stdout.write(
                    f"  - {product.name}"
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.ERROR(
                "WARNING: This will remove unused products "
                "and deactivate purchased products."
            )
        )

        self.stdout.write(
            self.style.WARNING(
                "Existing orders and order items will NOT be deleted."
            )
        )

        confirmation = input(
            "\nType DELETE to continue: "
        )

        if confirmation != "DELETE":

            self.stdout.write(
                self.style.ERROR(
                    "Operation aborted."
                )
            )

            return

        # ---------------------------------------------------------
        # Database operation
        # ---------------------------------------------------------

        with transaction.atomic():

            # -----------------------------------------------------
            # Preserve purchased products but remove them from
            # the active storefront.
            # -----------------------------------------------------

            if purchased_count > 0:

                purchased_products.update(
                    is_active=False
                )

            # -----------------------------------------------------
            # Permanently delete products that have never been
            # referenced by an order.
            # -----------------------------------------------------

            if unused_count > 0:

                unused_products.delete()

        # ---------------------------------------------------------
        # Delete image files belonging to deleted products
        # ---------------------------------------------------------

        deleted_images = 0

        for path in image_paths:

            try:

                if os.path.exists(path):

                    os.remove(path)
                    deleted_images += 1

            except OSError as e:

                self.stdout.write(
                    self.style.WARNING(
                        f"Failed to delete image {path}: {e}"
                    )
                )

        # ---------------------------------------------------------
        # Final statistics
        # ---------------------------------------------------------

        remaining_products = Product.objects.count()
        active_products = Product.objects.filter(
            is_active=True
        ).count()

        inactive_products = Product.objects.filter(
            is_active=False
        ).count()

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "========================================"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Product catalog cleanup completed."
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Unused products deleted: {unused_count}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Purchased products preserved: {purchased_count}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Images deleted: {deleted_images}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Active products remaining: {active_products}"
            )
        )

        self.stdout.write(
            self.style.WARNING(
                f"Inactive historical products: {inactive_products}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Total products remaining: {remaining_products}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Existing orders and order history were preserved."
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                "========================================"
            )
        )