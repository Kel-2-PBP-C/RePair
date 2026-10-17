from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0006_profile_onboarding_completed_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='domicile_code',
            field=models.CharField(blank=True, max_length=20, verbose_name='Kode wilayah domisili'),
        ),
    ]
