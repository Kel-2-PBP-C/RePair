from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="email_notifications",
            field=models.BooleanField(default=True, verbose_name="Notifikasi email"),
        ),
        migrations.AddField(
            model_name="profile",
            name="profile_visibility",
            field=models.BooleanField(default=True, verbose_name="Profil dapat dilihat pengguna lain"),
        ),
        migrations.AddField(
            model_name="profile",
            name="language",
            field=models.CharField(
                choices=[("id", "Bahasa Indonesia"), ("en", "English")],
                default="id", max_length=2, verbose_name="Bahasa",
            ),
        ),
    ]
