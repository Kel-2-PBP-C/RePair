from django import forms
from .models import Bid

class BidForm(forms.ModelForm):
    class Meta:
        model = Bid
        fields = [
            'replacement_type', 'replacement_item', 'replacement_description',
            'replacement_thumbnail', 'item_year', 'condition',
        ]
        labels = {
            'replacement_type': 'Jenis penawaran',
            'replacement_item': 'Nama barang / jasa',
            'replacement_description': 'Deskripsi',
            'replacement_thumbnail': 'URL foto',
            'item_year': 'Tahun barang',
            'condition': 'Kondisi (%)',
        }
        widgets = {
            'replacement_description': forms.Textarea(attrs={'rows': 3}),
        }