from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User

from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from accounts.models import Profile


class PostQuerySet(models.QuerySet):
    def for_forum(self):
        """
        Filter for Forum (FYP) / main_page:
        Only returns posts with status AVAILABLE.
        """
        return self.filter(status=Post.StatusChoices.AVAILABLE)


class Post(models.Model):
    class ConditionChoices(models.TextChoices):
        NEW = 'NEW', 'Baru'
        GOOD = 'GOOD', 'Bekas - Layak Pakai'
        REPAIR = 'REPAIR', 'Butuh Perbaikan (RePair)'

    class ShippingChoices(models.TextChoices):
        COD = 'COD', 'COD / Ketemuan Langsung'
        INSTANT = 'INSTANT', 'Instan / Same Day (< 1 Hari)'
        REGULAR = 'REGULAR', 'Reguler (2 - 4 Hari)'

    class StatusChoices(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Tersedia'
        NEGOTIATING = 'NEGOTIATING', 'Dalam Negosiasi'
        BARTERED = 'BARTERED', 'Sudah Dibarter'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile_posts'
    )
    title = models.CharField(max_length=150)
    description = models.TextField()
    category = models.CharField(
        max_length=20,
        choices=Profile.CATEGORY_CHOICES,
        blank=True,
        default='',
    )
    image_url = models.URLField(
        max_length=500,
        blank=True,
        default='https://placehold.co/300x300/e3f4ea/0d5c31?text=RePair+Item'
    )
    # Structured region code & human-readable label (synced with accounts/regions.py)
    location_code = models.CharField(max_length=32, blank=True, db_index=True)
    location = models.CharField(max_length=150)

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
        default=StatusChoices.AVAILABLE,
        editable=True
    )
    preferred_barter = models.CharField(
        max_length=150,
        help_text="Barang yang dicari sebagai tukaran (item_replacement)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    objects = PostQuerySet.as_manager()

    @property
    def item_replacement(self):
        """Compatibility alias for barter_details app."""
        return self.preferred_barter

    @item_replacement.setter
    def item_replacement(self, value):
        self.preferred_barter = value

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"


class BarterOffer(models.Model):
    """Stores incoming barter offers/bids for a Post."""
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='offers')
    offerer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='barter_offers'
    )
    offered_item_title = models.CharField(max_length=150)
    offered_item_description = models.TextField()
    offerer_contact = models.CharField(max_length=100, help_text="Kontak penawar")
    is_selected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tawaran {self.offered_item_title} oleh {self.offerer.username}"


class BarterReview(models.Model):
    """Stores post-barter feedback, currently submitted by the post owner."""
    class RoleChoices(models.TextChoices):
        OWNER_TO_OFFERER = 'OWNER_TO_OFFERER', 'Review ke Penawar'
        OFFERER_TO_OWNER = 'OFFERER_TO_OWNER', 'Review ke Pembuat Post'

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='given_reviews'
    )
    reviewee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_reviews'
    )
    role = models.CharField(max_length=20, choices=RoleChoices.choices)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['post', 'role'], name='unique_review_per_role')
        ]


class BarterTransaction(models.Model):
    """
    Model pendukung untuk menghitung statistik Total Rating & Total Barter (M/Y/A).
    Jika timmu sudah memiliki model transaksi/review di app lain, 
    kamu cukup mengimpor model milik temanmu di views.py.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='barter_transactions')
    rating = models.FloatField(default=5.0)
    completed_at = models.DateTimeField(auto_now_add=True)