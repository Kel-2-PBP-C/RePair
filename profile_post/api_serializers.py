from django.utils.html import strip_tags
from rest_framework import serializers

from accounts.models import Profile
from .forms import resolve_region_from_accounts
from .models import BarterOffer, BarterReview, Post
from .views import _get_offer_contact


class PostSerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)
    offers_count = serializers.SerializerMethodField()
    category_label = serializers.SerializerMethodField()
    condition_label = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    selected_offer = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    category = serializers.ChoiceField(
        choices=Profile.CATEGORY_CHOICES,
        allow_blank=True,
        required=False,
    )
    thumbnail = serializers.URLField(
        required=False,
        allow_blank=True,
        max_length=500,
    )
    item_location = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
    )
    location_code = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=32,
    )

    class Meta:
        model = Post
        fields = (
            'id',
            'owner',
            'title',
            'description',
            'thumbnail',
            'item_location',
            'location_code',
            'category',
            'category_label',
            'condition',
            'condition_label',
            'status',
            'status_label',
            'item_replacement',
            'selected_offer',
            'reviews',
            'completed_at',
            'created_at',
            'updated_at',
            'offers_count',
        )
        read_only_fields = (
            'id',
            'owner',
            'status',
            'completed_at',
            'created_at',
            'updated_at',
            'offers_count',
        )

    def validate(self, attrs):
        if self.instance is None and not attrs.get('category'):
            raise serializers.ValidationError({'category': 'This field is required.'})
        if (
            self.instance is not None
            and 'category' in attrs
            and self.instance.category
            and not attrs['category']
        ):
            raise serializers.ValidationError({'category': 'This field is required.'})

        if 'location_code' in attrs or 'item_location' in attrs:
            code = attrs.get(
                'location_code',
                self.instance.location_code if self.instance else '',
            )
            label = attrs.get(
                'item_location',
                self.instance.item_location if self.instance else '',
            )
            resolved_code, resolved_label = resolve_region_from_accounts(code, label)
            attrs['location_code'] = resolved_code
            attrs['item_location'] = resolved_label

        return attrs

    def get_offers_count(self, post):
        if hasattr(post, 'offers_count'):
            return post.offers_count
        return post.offers.count()

    def get_category_label(self, post):
        return post.get_category_display() if post.category else ''

    def get_condition_label(self, post):
        return post.get_condition_display()

    def get_status_label(self, post):
        return post.get_status_display()

    def get_selected_offer(self, post):
        offer = next(
            (item for item in post.offers.all() if item.is_selected),
            None,
        )
        if offer is None:
            return None
        return {
            'id': offer.pk,
            'offerer_name': offer.offerer.get_full_name() or offer.offerer.username,
            'offerer_contact': _get_offer_contact(offer),
            'offered_item_title': offer.offered_item_title,
            'offered_item_description': offer.offered_item_description,
        }

    def get_reviews(self, post):
        reviews = list(post.reviews.all())
        owner_review = next(
            (
                review
                for review in reviews
                if review.role == BarterReview.RoleChoices.OWNER_TO_OFFERER
            ),
            None,
        )
        offerer_review = next(
            (
                review
                for review in reviews
                if review.role == BarterReview.RoleChoices.OFFERER_TO_OWNER
            ),
            None,
        )
        return {
            'to_offerer': self._review_data(owner_review),
            'to_owner': self._review_data(offerer_review),
        }

    @staticmethod
    def _review_data(review):
        if review is None:
            return None
        return {'rating': review.rating, 'comment': review.comment}

    def validate_title(self, value):
        return strip_tags(value).strip()

    def validate_description(self, value):
        return strip_tags(value).strip()

    def validate_item_replacement(self, value):
        return strip_tags(value).strip()


class BarterOfferSerializer(serializers.ModelSerializer):
    offerer_name = serializers.SerializerMethodField()
    offerer_domicile = serializers.SerializerMethodField()
    offerer_contact = serializers.SerializerMethodField()

    class Meta:
        model = BarterOffer
        fields = (
            'id',
            'offerer_name',
            'offerer_domicile',
            'offerer_contact',
            'offered_item_title',
            'offered_item_description',
            'offered_item_thumbnail',
            'offered_item_location',
            'offered_item_location_code',
            'offered_item_category',
            'offered_item_condition',
            'is_selected',
            'created_at',
        )

    def get_offerer_name(self, offer):
        return offer.offerer.get_full_name() or offer.offerer.username

    def get_offerer_domicile(self, offer):
        profile = getattr(offer.offerer, 'profile', None)
        if profile is None:
            return ''
        return profile.domicile

    def get_offerer_contact(self, offer):
        return _get_offer_contact(offer)
