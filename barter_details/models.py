import uuid

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, MinLengthValidator
from datetime import date

def current_year():
    return date.today().year

class Barter(models.Model):
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
        
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='barter_items',)
    thumbnail = models.URLField(max_length=500)
    title= models.CharField(max_length=255)
    description = models.TextField(validators=[MinLengthValidator(5)])
    condition = models.CharField(
        max_length=10, 
        choices=ConditionChoices.choices, 
        default=ConditionChoices.GOOD
    )
    condition_percentage = models.PositiveIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Kondisi barang dalam persen (0-100)",
    )
    shipping_method = models.CharField(
        max_length=10, 
        choices=ShippingChoices.choices, 
        default=ShippingChoices.COD
    )
    status = models.CharField(
        max_length=15, 
        choices=StatusChoices.choices, 
        default=StatusChoices.AVAILABLE
    )
    item_year = models.PositiveIntegerField(validators=[MinValueValidator(1900), MaxValueValidator(current_year)],)
    item_replacement = models.CharField(max_length=255, blank=True)
    item_location= models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

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
    replacement_description = models.TextField(validators=[MinLengthValidator(5)])
    replacement_thumbnail = models.URLField(max_length=500, blank=True)
    
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
            if not self.replacement_thumbnail:
                errors['replacement_thumbnail'] = 'Foto wajib diisi untuk barang.'
            if self.item_year is None:
                errors['item_year'] = 'Tahun wajib diisi untuk barang.'
            if not self.condition:
                errors['condition'] = 'Kondisi wajib diisi untuk barang.'
            if self.condition_percentage is None:
                errors['condition_percentage'] = 'Persentase kondisi wajib diisi untuk barang.'
            if errors:
                raise ValidationError(errors)
        else:
            self.replacement_thumbnail = ''
            self.item_year = None
            self.condition = ''
            self.condition_percentage = None
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
            
    def __str__(self):
        return str(self.target)
