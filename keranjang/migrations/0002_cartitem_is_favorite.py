from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('keranjang', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='cartitem',
            name='is_favorite',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterModelOptions(
            name='cartitem',
            options={'ordering': ['-is_favorite', '-created_at']},
        ),
    ]
