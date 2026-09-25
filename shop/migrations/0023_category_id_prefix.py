from django.db import migrations, models


def fill_prefixes(apps, schema_editor):
    """Give every existing category the prefix its products' IDs already
    used (first six letters/digits of the name), so no ID a customer or a
    sales record has seen changes until staff choose a new prefix."""
    from shop.utils import derive_id_prefix

    Category = apps.get_model('shop', 'Category')
    taken = []
    for category in Category.objects.order_by('id'):
        category.id_prefix = derive_id_prefix(category.name, taken)
        category.save(update_fields=['id_prefix'])
        taken.append(category.id_prefix)


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0022_specifications_as_ordered_pairs'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='id_prefix',
            field=models.CharField(default='', max_length=10, verbose_name='ID prefix'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='category',
            name='id_digits',
            field=models.PositiveSmallIntegerField(default=1, help_text='Minimum digits in the number; shorter numbers get leading zeros (3 gives L-007).', verbose_name='Number length'),
        ),
        migrations.RunPython(fill_prefixes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='category',
            name='id_prefix',
            field=models.CharField(help_text='Start of every product ID in this category, e.g. L gives L-1, L-2, …', max_length=10, unique=True, verbose_name='ID prefix'),
        ),
    ]
