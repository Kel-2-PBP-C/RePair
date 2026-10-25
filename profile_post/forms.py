from django import forms
from .models import Post

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = [
            'title', 'description', 'image_url', 
            'location', 'condition', 'shipping_duration', 
            'status', 'preferred_barter'
        ]