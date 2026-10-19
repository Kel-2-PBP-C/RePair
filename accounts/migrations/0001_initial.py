from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Profile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("domicile", models.CharField(blank=True, max_length=150, verbose_name="Domisili")),
                ("birth_date", models.DateField(blank=True, null=True, verbose_name="Tanggal lahir")),
                ("social_contact", models.CharField(blank=True, max_length=200, verbose_name="Kontak media sosial")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
