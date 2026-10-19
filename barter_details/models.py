import uuid

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, MinLengthValidator

# Create your models here.
class Barter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='barter_items',)
    thumbnail = models.URLField(max_length=500)
    title= models.CharField(max_length=255)
    description = models.TextField(validators=[MinLengthValidator(5)])
    item_year = models.PositiveIntegerField()
    condition = models.PositiveIntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], help_text="Kondisi barang dalam persen (0-100)",)
    item_replacement = models.CharField(max_length=255, blank=True, null=True)
    item_location= models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
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
        
    id= models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target = models.ForeignKey('Barter', on_delete=models.CASCADE, related_name='bids_received')
    bidder = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bids')
    
    replacement_type = models.CharField(max_length=10, choices=ReplacementType.choices, default=ReplacementType.GOODS,)
    replacement_item = models.CharField(max_length=255)
    replacement_description = models.TextField(validators=[MinLengthValidator(5)])
    
    replacement_thumbnail = models.URLField(max_length=500, blank=True)
    item_year= models.PositiveIntegerField(blank=True, null=True)
    condition= models.PositiveIntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)], help_text="Kondisi barang dalam persen (0-100)",)
    
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
        
    def clean(self):
        if self.replacement_type == self.ReplacementType.GOODS:
            errors = {}
            if not self.replacement_thumbnail:
                errors['replacement_thumbnail'] = 'Foto wajib diisi untuk barang.'
            if self.item_year is None:
                errors['item_year'] = 'Tahun wajib diisi untuk barang.'
            if self.condition is None:
                errors['condition'] = 'Kondisi wajib diisi untuk barang.'
            if errors:
                raise ValidationError(errors)
        else:
            self.item_year = None
            self.condition = None
            
    def __str__(self):
        return str(self.target)