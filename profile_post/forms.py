from django import forms
from django.utils.html import strip_tags
from accounts.models import Profile
from accounts.regions import RegionServiceError
from .models import Post


def resolve_region_from_accounts(code: str, fallback_label: str = ''):
    """
    Resolves a region code and display name using accounts.regions.
    Returns (code, label).
    """
    clean_code = strip_tags(code or '').strip()
    clean_label = strip_tags(fallback_label or '').strip()

    try:
        from accounts import regions as acc_regions
        # Check common lookup functions in accounts/regions.py
        for fn_name in ('get_region_label', 'get_region_name', 'get_domicile_label', 'get_by_code', 'resolve_region'):
            fn = getattr(acc_regions, fn_name, None)
            if callable(fn) and clean_code:
                res = fn(clean_code)
                if isinstance(res, dict):
                    return clean_code, res.get('name') or res.get('label') or clean_label
                if isinstance(res, str) and res:
                    return clean_code, res
    except (ImportError, RegionServiceError, ValueError):
        pass

    return clean_code, clean_label


class PostForm(forms.ModelForm):
    location_code = forms.CharField(
        max_length=32,
        required=False,
        widget=forms.HiddenInput(),
    )
    category = forms.ChoiceField(choices=Profile.CATEGORY_CHOICES, required=False)

    class Meta:
        model = Post
        labels = {
            'title': 'Nama barang',
            'description': 'Deskripsi',
            'thumbnail': 'URL foto',
            'location_code': 'Kode wilayah',
            'item_location': 'Lokasi',
            'category': 'Kategori',
            'condition': 'Kondisi',
            'item_replacement': 'Barang yang dicari',
        }
        fields = [
            'title', 'description', 'thumbnail',
            'location_code', 'item_location', 'category', 'condition',
            'item_replacement',
        ]
        widgets = {
            'item_location': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        self.mark_as_profile_post = kwargs.pop('mark_as_profile_post', True)
        data = kwargs.get('data')
        positional_data = args[0] if args else None
        bound_data = data if data is not None else positional_data
        if bound_data is not None:
            bound_data = bound_data.copy()
            for alias, field_name in (
                ('image_url', 'thumbnail'),
                ('location', 'item_location'),
                ('preferred_barter', 'item_replacement'),
            ):
                if field_name not in bound_data and alias in bound_data:
                    bound_data[field_name] = bound_data[alias]
            if data is not None:
                kwargs['data'] = bound_data
            else:
                args = (bound_data, *args[1:])
        super().__init__(*args, **kwargs)
        self.fields['category'].required = self.instance._state.adding or bool(
            self.instance.category
        )

    def clean_title(self):
        return strip_tags(self.cleaned_data.get('title', '')).strip()

    def clean_description(self):
        return strip_tags(self.cleaned_data.get('description', '')).strip()

    def clean_item_replacement(self):
        return strip_tags(self.cleaned_data.get('item_replacement', '')).strip()

    def clean(self):
        cleaned_data = super().clean()
        code = cleaned_data.get('location_code', '')
        label = cleaned_data.get('item_location', '')
        resolved_code, resolved_label = resolve_region_from_accounts(code, label)
        cleaned_data['location_code'] = resolved_code
        cleaned_data['item_location'] = resolved_label
        return cleaned_data

    def save(self, commit=True):
        post = super().save(commit=False)
        if self.mark_as_profile_post:
            post.is_profile_post = True
        if commit:
            post.save()
            self.save_m2m()
        return post