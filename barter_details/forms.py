from django import forms
from accounts.models import Profile
from .models import Bid


class BidForm(forms.ModelForm):
    replacement_item = forms.CharField(
        max_length=255,
        label='Nama barang',
    )
    replacement_description = forms.CharField(
        label='Deskripsi',
        widget=forms.Textarea(attrs={'rows': 3}),
    )
    replacement_thumbnail = forms.URLField(
        required=False,
        label='URL foto (opsional)',
    )
    replacement_location = forms.CharField(
        max_length=150,
        label='Lokasi',
        widget=forms.TextInput(
            attrs={'id': 'bid-region-search', 'autocomplete': 'off'}
        ),
    )
    replacement_location_code = forms.CharField(
        max_length=32,
        label='Kode wilayah',
        widget=forms.HiddenInput(),
    )
    replacement_category = forms.ChoiceField(
        choices=Profile.CATEGORY_CHOICES,
        label='Kategori barang',
    )
    condition = forms.ChoiceField(
        choices=Bid.ConditionChoices.choices,
        label='Kondisi',
    )

    class Meta:
        model = Bid
        fields = [
            'replacement_type', 'replacement_item', 'replacement_description',
            'replacement_thumbnail', 'replacement_location',
            'replacement_location_code',
            'replacement_category', 'condition',
        ]
        widgets = {
            'replacement_type': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial.setdefault(
            'replacement_type',
            Bid.ReplacementType.GOODS,
        )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('replacement_location') and not cleaned_data.get(
            'replacement_location_code'
        ):
            self.add_error(
                'replacement_location',
                'Pilih wilayah dari daftar.',
            )
        return cleaned_data