from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User

class Post(models.Model):
    class ConditionChoices(models.TextChoices):
        NEW = 'NEW', 'Baru'
        GOOD = 'GOOD', 'Bekas - Layak Pakai'
        REPAIR = 'REPAIR', 'Butuh Perbaikan'

    class ShippingChoices(models.TextChoices):
        COD = 'COD', 'COD / Temu Langsung'
        PACKAGED = 'PACKAGED', 'Dipaketkan'

    class StatusChoices(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Tersedia'
        NEGOTIATING = 'NEGOTIATING', 'Dalam Negosiasi'
        BARTERED = 'BARTERED', 'Sudah Dibarter'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    title = models.CharField(max_length=150)
    description = models.TextField()
    image_url = models.URLField(
        max_length=500, 
        blank=True, 
        default='https://placehold.co/300x300/e2e8f0/475569?text=Barang'
    )
    location = models.CharField(max_length=100)
    condition = models.CharField(
        max_length=10, 
        choices=ConditionChoices.choices, 
        default=ConditionChoices.GOOD
    )
    shipping_duration = models.CharField(
        max_length=10, 
        choices=ShippingChoices.choices, 
        default=ShippingChoices.COD
    )
    status = models.CharField(
        max_length=15, 
        choices=StatusChoices.choices, 
        default=StatusChoices.AVAILABLE
    )
    preferred_barter = models.CharField(
        max_length=150, 
        help_text="Barang yang dicari sebagai tukaran"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.user.username}"


class BarterTransaction(models.Model):
    """
    Model pendukung untuk menghitung statistik Total Rating & Total Barter (M/Y/A).
    Jika timmu sudah memiliki model transaksi/review di app lain, 
    kamu cukup mengimpor model milik temanmu di views.py.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='barter_transactions')
    rating = models.FloatField(default=5.0)
    completed_at = models.DateTimeField(auto_now_add=True)