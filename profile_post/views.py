from datetime import timedelta
import uuid

from django.http import Http404
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Count
from django.utils import timezone
from django.utils import formats, translation
from django.utils.timesince import timesince
from django.utils.html import strip_tags
from django.urls import reverse, NoReverseMatch

from accounts.models import Profile
from accounts.utils import profile_initials
from .models import Post, BarterOffer, BarterReview
from .forms import PostForm, resolve_region_from_accounts

User = get_user_model()

# Fallback Indonesian regions if accounts.regions is not yet populated in test DB
FALLBACK_REGIONS = [
    {'code': '3171', 'name': 'Jakarta Pusat, DKI Jakarta'},
    {'code': '3172', 'name': 'Jakarta Utara, DKI Jakarta'},
    {'code': '3173', 'name': 'Jakarta Barat, DKI Jakarta'},
    {'code': '3174', 'name': 'Jakarta Selatan, DKI Jakarta'},
    {'code': '3175', 'name': 'Jakarta Timur, DKI Jakarta'},
    {'code': '3276', 'name': 'Kota Depok, Jawa Barat'},
    {'code': '3271', 'name': 'Kota Bogor, Jawa Barat'},
    {'code': '3275', 'name': 'Kota Bekasi, Jawa Barat'},
    {'code': '3273', 'name': 'Kota Bandung, Jawa Barat'},
    {'code': '3671', 'name': 'Kota Tangerang, Banten'},
    {'code': '3674', 'name': 'Kota Tangerang Selatan, Banten'},
    {'code': '3578', 'name': 'Kota Surabaya, Jawa Timur'},
]


def _get_user_contact(user):
    """Returns the user's explicitly saved preferred contact, never their email."""
    profile = getattr(user, 'profile', None)
    return (getattr(profile, 'social_contact', '') or '').strip()


def _get_offer_contact(offer):
    contact = (offer.offerer_contact or '').strip()
    email = (offer.offerer.email or '').strip()
    if not contact or contact.casefold() == email.casefold():
        contact = _get_user_contact(offer.offerer)
    return contact or 'Kontak belum diatur'


def _format_created_at(value):
    with translation.override('id'):
        return (
            formats.date_format(value, 'j F Y, H:i'),
            f'{timesince(value)} yang lalu',
        )


def _get_user_default_region(user):
    """
    Reads default domicile_code and human-readable domicile name from accounts.Profile.
    Returns (code, label).
    """
    profile = getattr(user, 'profile', None)
    if profile:
        code = getattr(profile, 'domicile_code', '') or ''
        label = (
            getattr(profile, 'domicile_name', '')
            or getattr(profile, 'domicile', '')
            or getattr(profile, 'location', '')
            or ''
        )
        resolved_code, resolved_label = resolve_region_from_accounts(str(code), str(label))
        if not resolved_label and resolved_code:
            for item in FALLBACK_REGIONS:
                if item['code'] == resolved_code:
                    resolved_label = item['name']
                    break
        if resolved_code or resolved_label:
            return resolved_code, (resolved_label or resolved_code)

    return '3174', 'Jakarta Selatan, DKI Jakarta'


def _query_accounts_regions(query: str):
    """
    Delegates region searching to accounts.regions (or falls back to FALLBACK_REGIONS)
    so the frontend uses the exact same region dataset as accounts.
    """
    q_lower = (query or '').strip().lower()
    results = []

    try:
        from accounts import regions as acc_regions
        # 1. Try search helper functions in accounts/regions.py
        for fn_name in ('search_regions', 'filter_regions', 'find_regions', 'get_regions'):
            fn = getattr(acc_regions, fn_name, None)
            if callable(fn):
                raw = fn(query) if fn.__code__.co_argcount >= 1 else fn()
                for item in raw:
                    if isinstance(item, dict):
                        code = str(item.get('code') or item.get('id') or item.get('domicile_code') or '')
                        name = str(item.get('name') or item.get('label') or item.get('display') or '')
                    elif isinstance(item, (list, tuple)) and len(item) >= 2:
                        code, name = str(item[0]), str(item[1])
                    else:
                        continue
                    if not q_lower or q_lower in name.lower() or q_lower in code.lower():
                        results.append({'code': code, 'name': name})
                if results:
                    return results[:25]

        # 2. Try iterable constants in accounts/regions.py
        for const_name in ('REGIONS', 'DOMICILE_CHOICES', 'INDONESIA_REGIONS', 'REGION_LIST'):
            data = getattr(acc_regions, const_name, None)
            if isinstance(data, dict):
                for code, name in data.items():
                    label = name.get('name') if isinstance(name, dict) else str(name)
                    if not q_lower or q_lower in label.lower() or q_lower in str(code).lower():
                        results.append({'code': str(code), 'name': label})
            elif isinstance(data, (list, tuple)):
                for item in data:
                    if isinstance(item, dict):
                        code = str(item.get('code') or item.get('id') or '')
                        label = str(item.get('name') or item.get('label') or '')
                    elif isinstance(item, (list, tuple)) and len(item) >= 2:
                        code, label = str(item[0]), str(item[1])
                    else:
                        continue
                    if not q_lower or q_lower in label.lower() or q_lower in code.lower():
                        results.append({'code': code, 'name': label})
            if results:
                return results[:25]
    except ImportError:
        pass

    # 3. Fallback to standard Indonesian cities/regencies
    for item in FALLBACK_REGIONS:
        if not q_lower or q_lower in item['name'].lower() or q_lower in item['code'].lower():
            results.append(item)
    return results[:25]


def _get_offers_for_post(post):
    return post.offers.select_related('offerer').all()


def _resolve_detail_url(post_id):
    for route_name in ('barter_details:details', 'barter_details:detail', 'profile_post:post_detail'):
        try:
            return reverse(route_name, args=[post_id])
        except NoReverseMatch:
            continue
    return f"/profile-post/{post_id}/"


def _get_post_or_404(post_id, **filters):
    try:
        post_uuid = uuid.UUID(str(post_id))
    except (AttributeError, TypeError, ValueError):
        if not str(post_id).isdigit():
            raise Http404
        lookup = {'legacy_profile_post_id': post_id}
    else:
        lookup = {'pk': post_uuid}
    return get_object_or_404(Post, **lookup, **filters)


def _localized_form_errors(form):
    message_by_code = {
        'required': 'Wajib diisi.',
        'invalid': 'Format yang dimasukkan tidak valid.',
        'invalid_choice': 'Pilih salah satu opsi yang tersedia.',
        'max_length': 'Maksimal {limit_value} karakter.',
        'min_length': 'Minimal {limit_value} karakter.',
        'min_value': 'Nilai minimal adalah {limit_value}.',
        'max_value': 'Nilai maksimal adalah {limit_value}.',
    }
    localized_errors = {}
    for field_name, errors in form.errors.as_data().items():
        field = form.fields.get(field_name)
        field_label = field.label if field else 'Formulir'
        messages = []
        for error in errors:
            template = message_by_code.get(error.code, 'Periksa kembali nilai yang dimasukkan.')
            params = error.params or {}
            try:
                message = template.format(**params)
            except (KeyError, ValueError):
                message = 'Periksa kembali nilai yang dimasukkan.'
            messages.append(f'{field_label}: {message}')
        localized_errors[field_label] = messages
    return localized_errors


def _calc_delta(current_val, prev_val, is_float=False):
    diff = round(current_val - prev_val, 1) if is_float else int(current_val - prev_val)
    if prev_val > 0:
        pct = round(((current_val - prev_val) / prev_val) * 100, 1)
    else:
        pct = 100.0 if current_val > 0 else 0.0
    return {
        'value': round(current_val, 1) if is_float else int(current_val),
        'diff': diff,
        'pct': pct,
        'direction': 'up' if diff > 0 else ('down' if diff < 0 else 'neutral')
    }


@login_required
def index(request):
    """Renders the main Posts page with inherited account contact and region."""
    default_code, default_label = _get_user_default_region(request.user)
    context = {
        'user': request.user,
        'profile_initials': profile_initials(request.user),
        'preferred_contact': _get_user_contact(request.user),
        'default_location_code': default_code,
        'default_location_label': default_label,
        'category_choices': Profile.CATEGORY_CHOICES,
    }
    return render(request, 'profile_post/index.html', context)


@login_required
def post_detail_page(request, post_id):
    post = _get_post_or_404(post_id, is_profile_post=True)
    selected_offer = post.offers.filter(is_selected=True).first()
    created_at_display, _ = _format_created_at(post.created_at)
    return render(request, 'profile_post/detail.html', {
        'post': post,
        'selected_offer': selected_offer,
        'created_at_display': created_at_display,
    })


@login_required
@require_GET
def search_regions_api(request):
    """
    API endpoint for searching regions in both the Filter Sidebar and Add/Edit Modal.
    Also attempts to delegate to accounts.region_views if a view is exposed there.
    """
    q = request.GET.get('q', '').strip()
    regions = _query_accounts_regions(q)
    return JsonResponse({'results': regions})


@login_required
@require_GET
def get_user_stats(request):
    period = request.GET.get('period', 'A').upper()
    now = timezone.now()

    all_posts = Post.objects.filter(owner=request.user, is_profile_post=True)
    all_barters = all_posts.filter(status=Post.StatusChoices.BARTERED)
    all_reviews = BarterReview.objects.filter(
        reviewee=request.user,
        role=BarterReview.RoleChoices.OWNER_TO_OFFERER,
    )

    if period in ['M', 'Y']:
        days = 30 if period == 'M' else 365
        curr_start = now - timedelta(days=days)
        prev_start = now - timedelta(days=days * 2)

        curr_posts = all_posts.filter(created_at__gte=curr_start).count()
        curr_barters = all_barters.filter(completed_at__gte=curr_start).count()
        curr_rating = all_reviews.filter(created_at__gte=curr_start).aggregate(avg=Avg('rating'))['avg'] or 0.0

        prev_posts = all_posts.filter(created_at__gte=prev_start, created_at__lt=curr_start).count()
        prev_barters = all_barters.filter(completed_at__gte=prev_start, completed_at__lt=curr_start).count()
        prev_rating = all_reviews.filter(created_at__gte=prev_start, created_at__lt=curr_start).aggregate(avg=Avg('rating'))['avg'] or 0.0

        return JsonResponse({
            'period': period,
            'show_delta': True,
            'rating': _calc_delta(curr_rating, prev_rating, is_float=True),
            'posts': _calc_delta(curr_posts, prev_posts),
            'barters': _calc_delta(curr_barters, prev_barters),
        })

    return JsonResponse({
        'period': 'A',
        'show_delta': False,
        'rating': {'value': round(all_reviews.aggregate(avg=Avg('rating'))['avg'] or 0.0, 1)},
        'posts': {'value': all_posts.count()},
        'barters': {'value': all_barters.count()},
    })


@login_required
@require_GET
def get_posts_json(request):
    queryset = Post.objects.filter(
        owner=request.user,
        is_profile_post=True,
    ).annotate(
        offers_count=Count('offers')
    ).prefetch_related('offers__offerer', 'reviews')

    q = request.GET.get('q', '').strip()
    if q:
        queryset = queryset.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(item_replacement__icontains=q)
        )

    # Filter by structured region code or region label
    location_code = request.GET.get('location_code', '').strip()
    location_label = request.GET.get('location', '').strip()
    if location_code and location_label:
        queryset = queryset.filter(
            Q(location_code=location_code) | Q(item_location__icontains=location_label)
        )
    elif location_code:
        queryset = queryset.filter(location_code=location_code)
    elif location_label:
        queryset = queryset.filter(item_location__icontains=location_label)

    condition = request.GET.get('condition', '').strip()
    if condition:
        queryset = queryset.filter(condition=condition)

    status = request.GET.get('status', '').strip()
    if status:
        queryset = queryset.filter(status=status)

    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'oldest':
        queryset = queryset.order_by('created_at')
    elif sort_by == 'offer':
        queryset = queryset.order_by('-offers_count', '-created_at')
    else:
        queryset = queryset.order_by('-created_at')

    page_number = int(request.GET.get('page', 1))
    paginator = Paginator(queryset, 5)
    page_obj = paginator.get_page(page_number)

    posts_data = []
    for post in page_obj:
        created_at_display, created_at_ago = _format_created_at(post.created_at)
        offers_list = list(_get_offers_for_post(post))
        selected_offer = next((o for o in offers_list if o.is_selected), None)
        review_to_offerer = next((r for r in post.reviews.all() if r.role == BarterReview.RoleChoices.OWNER_TO_OFFERER), None)

        posts_data.append({
            'id': post.id,
            'title': post.title,
            'description': post.description,
            'image_url': post.image_url or 'https://placehold.co/300x300/e3f4ea/0d5c31?text=RePair+Item',
            'detail_url': _resolve_detail_url(post.id),
            'location_code': post.location_code,
            'location': post.location,
            'category_code': post.category,
            'category_label': post.get_category_display() if post.category else '',
            'condition_code': post.condition,
            'condition_label': post.get_condition_display(),
            'status_code': post.status,
            'status_label': post.get_status_display(),
            'preferred_barter': post.preferred_barter,
            'created_at_display': created_at_display,
            'created_at_ago': created_at_ago,
            'offers_count': len(offers_list),
            'selected_offer': {
                'id': selected_offer.id,
                'offerer_name': selected_offer.offerer.get_full_name() or selected_offer.offerer.username,
                'offerer_contact': _get_offer_contact(selected_offer),
                'offered_item_title': selected_offer.offered_item_title,
                'offered_item_description': selected_offer.offered_item_description,
            } if selected_offer else None,
            'reviews': {
                'to_offerer': {
                    'rating': review_to_offerer.rating,
                    'comment': review_to_offerer.comment,
                } if review_to_offerer else None,
            }
        })

    return JsonResponse({
        'posts': posts_data,
        'has_next': page_obj.has_next(),
        'current_page': page_obj.number,
    })


@login_required
@require_GET
def get_forum_posts_json(request):
    forum_posts = Post.objects.for_forum().select_related('owner').order_by('-created_at')[:20]
    data = [{
        'id': p.id,
        'title': p.title,
        'owner': p.user.username,
        'location_code': p.location_code,
        'location': p.location,
        'category_code': p.category,
        'category_label': p.get_category_display() if p.category else '',
        'preferred_barter': p.preferred_barter,
        'status': p.get_status_display(),
    } for p in forum_posts]
    return JsonResponse({'forum_posts': data})


@login_required
@require_POST
def create_post_ajax(request):
    form = PostForm(request.POST)
    if form.is_valid():
        post = form.save(commit=False)
        post.owner = request.user
        post.status = Post.StatusChoices.AVAILABLE

        # Inherit default region from account profile if not explicitly chosen
        if not post.location_code and not post.location:
            default_code, default_label = _get_user_default_region(request.user)
            post.location_code = default_code
            post.location = default_label
        elif post.location_code and not post.location:
            post.location = resolve_region_from_accounts(post.location_code, post.location_code)

        if not post.image_url:
            post.image_url = 'https://placehold.co/300x300/e3f4ea/0d5c31?text=RePair+Item'
        post.save()
        return JsonResponse({'status': 'success'}, status=201)
    return JsonResponse(
        {'status': 'error', 'errors': _localized_form_errors(form)},
        status=400,
    )


@login_required
@require_POST
def edit_post_ajax(request, post_id):
    post = _get_post_or_404(post_id, owner=request.user, is_profile_post=True)
    if post.status != Post.StatusChoices.AVAILABLE:
        return JsonResponse({'status': 'error', 'message': 'Post tidak dapat diedit saat negosiasi/sudah dibarter.'}, status=400)

    form = PostForm(request.POST, instance=post)
    if form.is_valid():
        updated_post = form.save(commit=False)
        if not updated_post.location_code and not updated_post.location:
            default_code, default_label = _get_user_default_region(request.user)
            updated_post.location_code = default_code
            updated_post.location = default_label
        updated_post.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse(
        {'status': 'error', 'errors': _localized_form_errors(form)},
        status=400,
    )


@login_required
@require_POST
def delete_post_ajax(request, post_id):
    post = _get_post_or_404(post_id, owner=request.user, is_profile_post=True)
    if post.status != Post.StatusChoices.AVAILABLE:
        return JsonResponse({'status': 'error', 'message': 'Post tidak dapat dihapus saat negosiasi/sudah dibarter.'}, status=400)

    post.delete()
    return JsonResponse({'status': 'success'})


@login_required
@require_GET
def get_post_offers_json(request, post_id):
    post = _get_post_or_404(post_id, owner=request.user, is_profile_post=True)

    if not _get_offers_for_post(post).exists():
        dummy_user1, _ = User.objects.get_or_create(username='budi_barter', defaults={'first_name': 'Budi Santoso'})
        dummy_user2, _ = User.objects.get_or_create(username='siti_kolektor', defaults={'first_name': 'Siti Rahma'})
        BarterOffer.objects.create(
            post=post,
            offerer=dummy_user1,
            offered_item_title=f"{post.preferred_barter} (Kondisi 95%)",
            offered_item_description="Pemakaian pribadi 3 bulan, fungsi normal semua, kelengkapan fullset.",
            offerer_contact=_get_user_contact(dummy_user1)
        )
        BarterOffer.objects.create(
            post=post,
            offerer=dummy_user2,
            offered_item_title=f"Alternatif: {post.preferred_barter} + Aksesoris",
            offered_item_description="Kondisi terawat, siap COD atau kirim via kurir instan.",
            offerer_contact=_get_user_contact(dummy_user2)
        )

    offers = [{
        'id': o.id,
        'offerer_name': o.offerer.get_full_name() or o.offerer.username,
        'offerer_contact': _get_offer_contact(o),
        'offered_item_title': o.offered_item_title,
        'offered_item_description': o.offered_item_description,
        'is_selected': o.is_selected,
        'created_at': _format_created_at(o.created_at)[0],
    } for o in _get_offers_for_post(post)]

    return JsonResponse({'post_title': post.title, 'offers': offers})


@login_required
@require_POST
def lock_barter_ajax(request, post_id):
    post = _get_post_or_404(post_id, owner=request.user, is_profile_post=True)
    if post.status == Post.StatusChoices.BARTERED:
        return JsonResponse({'status': 'error', 'message': 'Barter sudah selesai.'}, status=400)

    offer_id = request.POST.get('offer_id')
    chosen_offer = get_object_or_404(BarterOffer, id=offer_id, post=post)

    post.offers.update(is_selected=False)
    chosen_offer.is_selected = True
    chosen_offer.save()

    post.status = Post.StatusChoices.NEGOTIATING
    post.save()
    return JsonResponse({'status': 'success'})


@login_required
@require_POST
def cancel_negotiation_ajax(request, post_id):
    post = _get_post_or_404(post_id, owner=request.user, is_profile_post=True)
    if post.status != Post.StatusChoices.NEGOTIATING:
        return JsonResponse({'status': 'error', 'message': 'Post tidak sedang dalam negosiasi.'}, status=400)

    post.offers.update(is_selected=False)
    post.status = Post.StatusChoices.AVAILABLE
    post.save()
    return JsonResponse({'status': 'success'})


@login_required
@require_POST
def complete_barter_ajax(request, post_id):
    post = _get_post_or_404(post_id, owner=request.user, is_profile_post=True)
    if post.status != Post.StatusChoices.NEGOTIATING:
        return JsonResponse({'status': 'error', 'message': 'Hanya post dalam negosiasi yang bisa diselesaikan.'}, status=400)

    post.status = Post.StatusChoices.BARTERED
    post.completed_at = timezone.now()
    post.save()
    return JsonResponse({'status': 'success'})


@login_required
@require_POST
def submit_review_ajax(request, post_id):
    post = _get_post_or_404(
        post_id,
        owner=request.user,
        is_profile_post=True,
        status=Post.StatusChoices.BARTERED,
    )
    selected_offer = post.offers.filter(is_selected=True).first()
    if not selected_offer:
        return JsonResponse({'status': 'error', 'message': 'Data penawar tidak ditemukan.'}, status=400)

    try:
        rating = max(1, min(5, int(request.POST.get('rating', 5))))
    except ValueError:
        rating = 5
    comment = strip_tags(request.POST.get('comment', '')).strip()

    BarterReview.objects.update_or_create(
        post=post,
        role=BarterReview.RoleChoices.OWNER_TO_OFFERER,
        defaults={
            'reviewer': post.user,
            'reviewee': selected_offer.offerer,
            'rating': rating,
            'comment': comment
        }
    )
    return JsonResponse({'status': 'success'})