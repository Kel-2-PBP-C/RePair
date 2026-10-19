from django.conf import settings
from django.db import models
from django.utils import timezone


class Profile(models.Model):
    CATEGORY_CHOICES = [
        ("elektronik", "Elektronik"), ("buku", "Buku"),
        ("pakaian", "Pakaian"), ("perabot", "Perabot"), ("hobi", "Hobi"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    domicile = models.CharField("Domisili", max_length=150, blank=True)
    domicile_code = models.CharField("Kode wilayah domisili", max_length=20, blank=True)
    birth_date = models.DateField("Tanggal lahir", null=True, blank=True)
    social_contact = models.CharField("Kontak media sosial", max_length=200, blank=True)
    email_notifications = models.BooleanField("Notifikasi email", default=True)
    profile_visibility = models.BooleanField("Profil dapat dilihat pengguna lain", default=True)
    language = models.CharField(
        "Bahasa", max_length=2, choices=[("id", "Bahasa Indonesia"), ("en", "English")], default="id"
    )
    credential_failed_attempts = models.PositiveIntegerField(default=0)
    credential_window_started = models.DateTimeField(null=True, blank=True)
    preferred_categories = models.JSONField("Kategori barang pilihan", default=list, blank=True)
    onboarding_completed = models.BooleanField("Pengisian profil awal selesai", default=False)

    def __str__(self):
        return f"Profil {self.user.username}"


class GoogleIdentity(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="google_identity"
    )
    subject = models.CharField(max_length=255, unique=True)
    email = models.EmailField(max_length=254, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Google: {self.user.get_username()}"


class GoogleLoginAttempt(models.Model):
    state_digest = models.CharField(max_length=64, primary_key=True)
    session_digest = models.CharField(max_length=64, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)


class GoogleAccountLinkChallenge(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, primary_key=True, on_delete=models.CASCADE,
        related_name='google_link_challenge',
    )
    token_digest = models.CharField(max_length=64, unique=True)
    session_digest = models.CharField(max_length=64)
    subject = models.CharField(max_length=255)
    email = models.EmailField(max_length=254)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    failed_attempts = models.PositiveIntegerField(default=0)
    window_started = models.DateTimeField(default=timezone.now)
