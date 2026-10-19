from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0003_google_identity_and_login_attempt'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='GoogleAccountLinkChallenge',
            fields=[
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='google_link_challenge', serialize=False, to=settings.AUTH_USER_MODEL)),
                ('token_digest', models.CharField(max_length=64, unique=True)),
                ('session_digest', models.CharField(max_length=64)),
                ('subject', models.CharField(max_length=255)),
                ('email', models.EmailField(max_length=254)),
                ('expires_at', models.DateTimeField()),
                ('consumed_at', models.DateTimeField(blank=True, null=True)),
                ('failed_attempts', models.PositiveIntegerField(default=0)),
                ('window_started', models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
    ]
