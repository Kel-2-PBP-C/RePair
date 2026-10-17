from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('barter_details', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='barter',
            name='item_replacement',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
