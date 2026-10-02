from django.conf import settings
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    domicile = models.CharField("Domisili", max_length=150, blank=True)
    birth_date = models.DateField("Tanggal lahir", null=True, blank=True)
    social_contact = models.CharField("Kontak media sosial", max_length=200, blank=True)
    email_notifications = models.BooleanField("Notifikasi email", default=True)
    profile_visibility = models.BooleanField("Profil dapat dilihat pengguna lain", default=True)
    language = models.CharField(
        "Bahasa", max_length=2, choices=[("id", "Bahasa Indonesia"), ("en", "English")], default="id"
    )

    def __str__(self):
        return f"Profil {self.user.username}"
