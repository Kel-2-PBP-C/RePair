from datetime import timedelta

from django.db import transaction
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.html import strip_tags
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response

from barter_details.models import Barter
from .api_serializers import BarterOfferSerializer, PostSerializer
from .forms import resolve_region_from_accounts
from .models import BarterOffer, BarterReview, Post
from .views import (
    _calc_delta,
    _get_post_or_404,
    _get_user_default_region,
    _query_accounts_regions,
)


class ProfilePostPagination(PageNumberPagination):
    page_size = 5


class ProfilePostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    permission_classes = (IsAuthenticated,)
    authentication_classes = (SessionAuthentication,)
    pagination_class = ProfilePostPagination
    lookup_value_regex = r'[0-9a-fA-F-]+'

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Post.objects.none()
        queryset = Post.objects.filter(
            owner=self.request.user,
            is_profile_post=True,
        ).annotate(
            offers_count=Count('offers'),
        ).prefetch_related(
            'offers__offerer',
            'offers__offerer__profile',
            'reviews',
        )

        query = self.request.query_params.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(item_replacement__icontains=query)
            )

        location_code = self.request.query_params.get('location_code', '').strip()
        location = self.request.query_params.get('location', '').strip()
        if location_code and location:
            queryset = queryset.filter(
                Q(location_code=location_code) | Q(item_location__icontains=location)
            )
        elif location_code:
            queryset = queryset.filter(location_code=location_code)
        elif location:
            queryset = queryset.filter(item_location__icontains=location)

        condition = self.request.query_params.get('condition', '').strip()
        if condition:
            queryset = queryset.filter(condition=condition)

        status = self.request.query_params.get('status', '').strip()
        if status:
            queryset = queryset.filter(status=status)

        sort_by = self.request.query_params.get('sort', 'newest')
        if sort_by == 'oldest':
            return queryset.order_by('created_at')
        if sort_by == 'offer':
            return queryset.order_by('-offers_count', '-created_at')
        return queryset.order_by('-created_at')

    def get_object(self):
        post_id = self.kwargs.get(self.lookup_url_kwarg or self.lookup_field)
        post = _get_post_or_404(
            post_id,
            owner=self.request.user,
            is_profile_post=True,
        )
        self.check_object_permissions(self.request, post)
        return post

    def perform_create(self, serializer):
        location_code = serializer.validated_data.get('location_code', '')
        location = serializer.validated_data.get('item_location', '')
        if not location_code and not location:
            location_code, location = _get_user_default_region(self.request.user)
        elif location_code and not location:
            _, location = resolve_region_from_accounts(location_code, location_code)

        thumbnail = serializer.validated_data.get('thumbnail')
        if not thumbnail:
            thumbnail = 'https://placehold.co/300x300/e3f4ea/0d5c31?text=RePair+Item'

        serializer.save(
            owner=self.request.user,
            is_profile_post=True,
            status=Barter.StatusChoices.AVAILABLE,
            location_code=location_code,
            item_location=location,
            thumbnail=thumbnail,
        )

    def update(self, request, *args, **kwargs):
        post = self.get_object()
        if post.status != Barter.StatusChoices.AVAILABLE:
            raise ValidationError(
                {'detail': 'Post tidak dapat diedit saat negosiasi/sudah dibarter.'}
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        post = self.get_object()
        if post.status != Barter.StatusChoices.AVAILABLE:
            raise ValidationError(
                {'detail': 'Post tidak dapat diedit saat negosiasi/sudah dibarter.'}
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        post = self.get_object()
        if post.status != Barter.StatusChoices.AVAILABLE:
            raise ValidationError(
                {'detail': 'Post tidak dapat dihapus saat negosiasi/sudah dibarter.'}
            )
        post.delete()
        return Response(status=204)

    @action(detail=True, methods=('get',), url_path='offers')
    def offers(self, request, pk=None):
        post = self.get_object()
        offers = post.offers.select_related('offerer', 'offerer__profile').all()
        serializer = BarterOfferSerializer(offers, many=True)
        return Response({
            'post_title': post.title,
            'offers': serializer.data,
        })

    @action(detail=False, methods=('get',), url_path='regions')
    def regions(self, request):
        query = request.query_params.get('q', '').strip()
        return Response({'results': _query_accounts_regions(query)})

    @action(detail=False, methods=('get',), url_path='stats')
    def stats(self, request):
        period = request.query_params.get('period', 'A').upper()
        now = timezone.now()
        all_posts = Post.objects.filter(owner=request.user, is_profile_post=True)
        all_reviews = BarterReview.objects.filter(reviewee=request.user)

        if period in ('M', 'Y'):
            days = 30 if period == 'M' else 365
            current_start = now - timedelta(days=days)
            previous_start = now - timedelta(days=days * 2)

            current_posts = all_posts.filter(created_at__gte=current_start).count()
            current_rating = (
                all_reviews.filter(created_at__gte=current_start)
                .aggregate(avg=Avg('rating'))['avg']
                or 0.0
            )
            previous_posts = all_posts.filter(
                created_at__gte=previous_start,
                created_at__lt=current_start,
            ).count()
            previous_rating = (
                all_reviews.filter(
                    created_at__gte=previous_start,
                    created_at__lt=current_start,
                ).aggregate(avg=Avg('rating'))['avg']
                or 0.0
            )

            return Response({
                'period': period,
                'show_delta': True,
                'rating': _calc_delta(current_rating, previous_rating, is_float=True),
                'posts': _calc_delta(current_posts, previous_posts),
            })

        return Response({
            'period': 'A',
            'show_delta': False,
            'rating': {
                'value': round(
                    all_reviews.aggregate(avg=Avg('rating'))['avg'] or 0.0,
                    1,
                )
            },
            'posts': {'value': all_posts.count()},
        })

    @action(detail=False, methods=('get',), url_path='forum')
    def forum(self, request):
        posts = Barter.objects.for_forum().select_related('owner').order_by('-created_at')[:20]
        return Response({
            'forum_posts': [{
                'id': post.id,
                'title': post.title,
                'owner': post.owner.username,
                'location_code': post.location_code,
                'location': post.location,
                'category_code': post.category,
                'category_label': post.get_category_display() if post.category else '',
                'preferred_barter': post.preferred_barter,
                'status': post.get_status_display(),
            } for post in posts]
        })

    @action(detail=True, methods=('post',), url_path='select-offer')
    def select_offer(self, request, pk=None):
        post = self.get_object()
        if post.status == Barter.StatusChoices.BARTERED:
            raise ValidationError({'detail': 'Barter sudah selesai.'})

        offer_id = request.data.get('offer_id')
        if not offer_id:
            raise ValidationError({'offer_id': 'This field is required.'})
        chosen_offer = get_object_or_404(BarterOffer, id=offer_id, post=post)

        with transaction.atomic():
            post.offers.update(is_selected=False)
            chosen_offer.is_selected = True
            chosen_offer.save(update_fields=['is_selected'])
            post.status = Barter.StatusChoices.NEGOTIATING
            post.save(update_fields=['status', 'updated_at'])
        return Response({'status': 'success'})

    @action(detail=True, methods=('post',), url_path='cancel-negotiation')
    def cancel_negotiation(self, request, pk=None):
        post = self.get_object()
        if post.status != Barter.StatusChoices.NEGOTIATING:
            raise ValidationError({'detail': 'Post tidak sedang dalam negosiasi.'})

        with transaction.atomic():
            post.offers.update(is_selected=False)
            post.status = Barter.StatusChoices.AVAILABLE
            post.save(update_fields=['status', 'updated_at'])
        return Response({'status': 'success'})

    @action(detail=True, methods=('post',), url_path='complete')
    def complete(self, request, pk=None):
        post = self.get_object()
        if post.status != Barter.StatusChoices.NEGOTIATING:
            raise ValidationError({
                'detail': 'Hanya post dalam negosiasi yang bisa diselesaikan.'
            })
        if not post.offers.filter(is_selected=True).exists():
            raise ValidationError({
                'detail': 'Pilih penawar sebelum menyelesaikan barter.'
            })

        post.status = Barter.StatusChoices.BARTERED
        post.completed_at = timezone.now()
        post.save(update_fields=['status', 'completed_at', 'updated_at'])
        return Response({'status': 'success'})

    @action(detail=True, methods=('post',), url_path='reviews')
    def reviews(self, request, pk=None):
        post = _get_post_or_404(pk, is_profile_post=True)
        is_owner = post.owner_id == request.user.pk
        selected_offer = post.offers.filter(is_selected=True).first()
        is_selected_offerer = (
            selected_offer is not None
            and selected_offer.offerer_id == request.user.pk
        )
        if not is_owner and not is_selected_offerer:
            raise NotFound()
        if post.status != Barter.StatusChoices.BARTERED:
            raise ValidationError({'detail': 'Barter belum selesai.'})
        if selected_offer is None:
            raise ValidationError({'detail': 'Data penawar tidak ditemukan.'})

        comment = strip_tags(request.data.get('comment', '')).strip()
        if is_owner:
            try:
                rating = max(1, min(5, int(request.data.get('rating', 5))))
            except (TypeError, ValueError):
                rating = 5
            review, created = BarterReview.objects.update_or_create(
                post=post,
                role=BarterReview.RoleChoices.OWNER_TO_OFFERER,
                defaults={
                    'reviewer': post.owner,
                    'reviewee': selected_offer.offerer,
                    'rating': rating,
                    'comment': comment,
                },
            )
        else:
            existing_review = BarterReview.objects.filter(
                post=post,
                role=BarterReview.RoleChoices.OFFERER_TO_OWNER,
            ).first()
            if existing_review:
                raise ValidationError({'detail': 'Kamu sudah mengirim ulasan untuk barter ini.'})

            try:
                rating = int(request.data.get('rating', ''))
            except (TypeError, ValueError):
                raise ValidationError({'rating': 'Pilih rating dari 1 sampai 5.'})
            if not 1 <= rating <= 5:
                raise ValidationError({'rating': 'Pilih rating dari 1 sampai 5.'})

            review = BarterReview.objects.create(
                post=post,
                reviewer=request.user,
                reviewee=post.owner,
                role=BarterReview.RoleChoices.OFFERER_TO_OWNER,
                rating=rating,
                comment=comment,
            )
            created = True

        return Response({
            'id': review.pk,
            'rating': review.rating,
            'comment': review.comment,
            'role': review.role,
        }, status=201 if created else 200)
