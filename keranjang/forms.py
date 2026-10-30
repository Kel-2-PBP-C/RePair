
from django import forms

from .models import CartItem


class FavoriteForm(forms.ModelForm):
    """
    Form untuk mengubah status favorit barang di keranjang.
    """

    class Meta:
        model = CartItem
        fields = ["is_favorite"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["is_favorite"].required = False
