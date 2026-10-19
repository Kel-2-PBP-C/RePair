import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('barter_details', '0002_barter_item_replacement'),
    ]

    operations = [
        migrations.AlterField(
            model_name='barter',
            name='description',
            field=models.TextField(validators=[django.core.validators.MinLengthValidator(5)]),
        ),
    ]
