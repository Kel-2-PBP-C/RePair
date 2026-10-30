import uuid
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import QuerySet

from accounts.models import Profile


def current_year():
    return date.today().year


class BarterQuerySet(QuerySet):
    def for_forum(self):
        return self.filter(
            is_profile_post=True,
            status=Barter.StatusChoices.AVAILABLE,
        )


class Barter(models.Model):
    class ConditionChoices(models.TextChoices):
        NEW = 'NEW', 'Baru'
        GOOD = 'GOOD', 'Bekas - Layak Pakai'
        REPAIR = 'REPAIR', 'Butuh Perbaikan'
    
    class StatusChoices(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Tersedia'
        NEGOTIATING = 'NEGOTIATING', 'Dalam Negosiasi'
        BARTERED = 'BARTERED', 'Sudah Dibarter'
        
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='barter_items',)
    thumbnail = models.URLField(
        max_length=500,
        blank=True,
        default='https://placehold.co/300x300/e3f4ea/0d5c31?text=RePair+Item',
    )
    title= models.CharField(max_length=255)
    description = models.TextField()
    condition = models.CharField(
        max_length=10, 
        choices=ConditionChoices.choices, 
        default=ConditionChoices.GOOD
    )
    condition_percentage = models.PositiveIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Kondisi barang dalam persen (0-100)",
    )
    status = models.CharField(
        max_length=15, 
        choices=StatusChoices.choices, 
        default=StatusChoices.AVAILABLE
    )
    item_year = models.PositiveIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1900), MaxValueValidator(current_year)],
    )
    item_replacement = models.CharField(max_length=255, blank=True)
    item_location = models.CharField(max_length=150)
    location_code = models.CharField(max_length=32, blank=True, db_index=True)
    category = models.CharField(
        max_length=20,
        choices=Profile.CATEGORY_CHOICES,
        blank=True,
        default='',
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    is_profile_post = models.BooleanField(default=False)
    legacy_profile_post_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        unique=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BarterQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']

    def __init__(self, *args, **kwargs):
        legacy_fields = {
            'user': 'owner',
            'image_url': 'thumbnail',
            'location': 'item_location',
            'preferred_barter': 'item_replacement',
        }
        is_profile_post = any(field in kwargs for field in legacy_fields)
        for legacy_name, field_name in legacy_fields.items():
            if legacy_name in kwargs:
                kwargs.setdefault(field_name, kwargs.pop(legacy_name))
        if is_profile_post:
            kwargs.setdefault('is_profile_post', True)
        super().__init__(*args, **kwargs)

    @property
    def user(self):
        return self.owner

    @user.setter
    def user(self, value):
        self.owner = value

    @property
    def image_url(self):
        return self.thumbnail

    @image_url.setter
    def image_url(self, value):
        self.thumbnail = value

    @property
    def location(self):
        return self.item_location

    @location.setter
    def location(self, value):
        self.item_location = value

    @property
    def preferred_barter(self):
        return self.item_replacement

    @preferred_barter.setter
    def preferred_barter(self, value):
        self.item_replacement = value

    def __str__(self):
        return self.title
    
class Bid(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Menunggu'
        ACCEPTED = 'accepted', 'Diterima'
        REJECTED = 'rejected', 'Ditolak'
    
    class ReplacementType(models.TextChoices):
        GOODS = 'goods', 'Barang'
        SERVICE = 'service', 'Jasa'
        
    class ConditionChoices(models.TextChoices):
        NEW = 'NEW', 'Baru'
        GOOD = 'GOOD', 'Bekas - Layak Pakai'
        REPAIR = 'REPAIR', 'Butuh Perbaikan'
        
    id= models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target = models.ForeignKey('Barter', on_delete=models.CASCADE, related_name='bids_received')
    bidder = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bids')
    
    replacement_type = models.CharField(max_length=10, choices=ReplacementType.choices, default=ReplacementType.GOODS,)
    replacement_item = models.CharField(max_length=255)
    replacement_description = models.TextField()
    replacement_thumbnail = models.URLField(max_length=500, blank=True)
    replacement_location = models.CharField(max_length=150, blank=True, default='')
    replacement_location_code = models.CharField(max_length=32, blank=True, default='')
    replacement_category = models.CharField(
        max_length=20,
        choices=Profile.CATEGORY_CHOICES,
        blank=True,
        default='',
    )
    
    item_year= models.PositiveIntegerField(blank=True, null=True, validators=[MinValueValidator(1900), MaxValueValidator(current_year)],)
    
    condition = models.CharField(
        blank=True,
        max_length=10, 
        choices=ConditionChoices.choices, 
    )
    condition_percentage= models.PositiveIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0),
        MaxValueValidator(100)],
        help_text="Kondisi barang dalam persen (0-100)",)
    
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
        
    def clean(self):
        if self.bidder_id and self.target_id and self.bidder_id == self.target.owner_id:
            raise ValidationError('Tidak bisa menawar barang sendiri.')
    
        if self.replacement_type == self.ReplacementType.GOODS:
            errors = {}
            if not self.condition:
                errors['condition'] = 'Kondisi wajib diisi untuk barang.'
            if errors:
                raise ValidationError(errors)
        else:
            self.replacement_thumbnail = ''
            self.item_year = None
            self.condition = ''
            self.condition_percentage = None
            self.replacement_location = ''
            self.replacement_location_code = ''
            self.replacement_category = ''
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
            
    def __str__(self):
        return str(self.target)
