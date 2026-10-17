from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_google_account_link_challenge"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="credential_failed_attempts",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="profile",
            name="credential_window_started",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
