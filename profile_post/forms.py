from django import forms
from django.utils.html import strip_tags
from accounts.models import Profile
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
    except ImportError:
        pass

    return clean_code, clean_label


class PostForm(forms.ModelForm):
    location_code = forms.CharField(max_length=32, required=False)
    location = forms.CharField(max_length=150, required=False)
    category = forms.ChoiceField(choices=Profile.CATEGORY_CHOICES, required=False)

    class Meta:
        model = Post
        fields = [
            'title', 'description', 'image_url',
            'location_code', 'location', 'category', 'condition',
            'preferred_barter'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].required = (
            self.instance._state.adding or bool(self.instance.category)
        )

    def clean_title(self):
        return strip_tags(self.cleaned_data.get('title', '')).strip()

    def clean_description(self):
        return strip_tags(self.cleaned_data.get('description', '')).strip()

    def clean_preferred_barter(self):
        return strip_tags(self.cleaned_data.get('preferred_barter', '')).strip()

    def clean(self):
        cleaned_data = super().clean()
        code = cleaned_data.get('location_code', '')
        label = cleaned_data.get('location', '')
        resolved_code, resolved_label = resolve_region_from_accounts(code, label)
        cleaned_data['location_code'] = resolved_code
        cleaned_data['location'] = resolved_label
        return cleaned_data