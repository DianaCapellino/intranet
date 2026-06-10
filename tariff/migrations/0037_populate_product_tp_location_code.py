from django.db import migrations


def populate_tp_location_code(apps, schema_editor):
    Product = apps.get_model('tariff', 'Product')
    updated = 0
    for product in (
        Product.objects
        .filter(tp_location_code='')
        .select_related('supplier__group__location', 'group__location')
    ):
        code = ''
        if (product.supplier and product.supplier.group and
                product.supplier.group.location):
            code = product.supplier.group.location.code
        elif product.group and product.group.location:
            code = product.group.location.code
        if code:
            product.tp_location_code = code
            product.save(update_fields=['tp_location_code'])
            updated += 1


class Migration(migrations.Migration):

    dependencies = [
        ('tariff', '0037_merge_20260604_1456'),
    ]

    operations = [
        migrations.RunPython(populate_tp_location_code, migrations.RunPython.noop),
    ]
