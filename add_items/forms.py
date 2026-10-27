from datetime import date
from django import forms
from barter_details.models import Barter

class BarterForm(forms.ModelForm):
    class Meta:
        model = Barter
        fields = ['title', 'description', 'thumbnail', 'item_year', 'condition', 'condition_percentage', 'shipping_method', 'item_location', 'item_replacement']
        labels = {
            'title': 'Nama Barang',
            'description': 'Deskripsi Barang',
            'thumbnail': 'URL Foto Barang',
            'item_year': 'Tahun Barang',
            'condition': 'Kondisi Barang',
            'condition_percentage': 'Kondisi Barang dalam Persentase (%)',
            'shipping_method': 'Metode Pengiriman',
            'item_location': 'Lokasi Barang',
            'item_replacement': 'Barang yang Diinginkan (Opsional)',
        }
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}
    
    def clean_item_year(self):
        year = self.cleaned_data['item_year']
        if not 1900 <= year <= date.today().year:
            raise forms.ValidationError('Tahun tidak valid')
        return year
        