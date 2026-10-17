from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0005_profile_credential_attempts'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='onboarding_completed',
            field=models.BooleanField(default=False, verbose_name='Pengisian profil awal selesai'),
        ),
        migrations.AddField(
            model_name='profile',
            name='preferred_categories',
            field=models.JSONField(blank=True, default=list, verbose_name='Kategori barang pilihan'),
        ),
    ]
