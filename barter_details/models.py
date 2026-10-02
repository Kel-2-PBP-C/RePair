import uuid

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator, MinLengthValidator

# Create your models here.
class Barter(models.Model):
    id= models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='barter_items',)
    thumbnail = models.URLField(max_length=500)
    title= models.CharField(max_length=255)
    description = models.TextField(validators=[MinLengthValidator(5)])
    item_year= models.PositiveIntegerField()
    condition= models.PositiveIntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)], help_text="Kondisi barang dalam persen (0-100)",)
    item_replacement= models.CharField(max_length=255, blank=True, null=True)
    item_location= models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title