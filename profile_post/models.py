from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from barter_details.models import Barter


Post = Barter


class BarterOffer(models.Model):
    """Stores incoming offers for a barter item."""

    post = models.ForeignKey(Barter, on_delete=models.CASCADE, related_name='offers')
    offerer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='barter_offers',
    )
    offered_item_title = models.CharField(max_length=255)
    offered_item_description = models.TextField()
    offered_item_thumbnail = models.URLField(max_length=500, blank=True, default='')
    offered_item_location = models.CharField(max_length=150, blank=True, default='')
    offered_item_location_code = models.CharField(max_length=32, blank=True, default='')
    offered_item_category = models.CharField(max_length=20, blank=True, default='')
    offered_item_condition = models.CharField(max_length=10, blank=True, default='')
    offerer_contact = models.CharField(max_length=100, blank=True, default='', help_text="Kontak penawar")
    is_selected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tawaran {self.offered_item_title} oleh {self.offerer.username}"


class BarterReview(models.Model):
    """Stores feedback submitted after a barter."""

    class RoleChoices(models.TextChoices):
        OWNER_TO_OFFERER = 'OWNER_TO_OFFERER', 'Review ke Penawar'
        OFFERER_TO_OWNER = 'OFFERER_TO_OWNER', 'Review ke Pembuat Post'

    post = models.ForeignKey(Barter, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='given_reviews',
    )
    reviewee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_reviews',
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
    """Stores user rating and completed-barter statistics."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='barter_transactions',
    )
    rating = models.FloatField(default=5.0)
    completed_at = models.DateTimeField(auto_now_add=True)
