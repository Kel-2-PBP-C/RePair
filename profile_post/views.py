from datetime import timedelta
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.core.paginator import Paginator
from django.db.models import Q, Avg
from django.utils import timezone

from .models import Post, BarterTransaction
from .forms import PostForm

@login_required
def show_posts_page(request):
    """Merender kerangka halaman utama Posts."""
    context = {
        'user': request.user,
        # Mengambil nomor telepon jika ada model profil tambahan, atau fallback default
        'phone_number': getattr(getattr(request.user, 'profile', None), 'phone', '0812-3456-7890'),
    }
    return render(request, 'profile_post/index.html', context)


@login_required
@require_GET
def get_user_stats(request):
    """
    Endpoint JSON untuk toggle statistik M (Month), Y (Year), A (All-time)
    pada kotak Rating, Posts, dan Barters.
    """
    period = request.GET.get('period', 'A').upper()
    now = timezone.now()

    posts_qs = Post.objects.filter(user=request.user)
    barters_qs = BarterTransaction.objects.filter(user=request.user)

    if period == 'M':
        start_date = now - timedelta(days=30)
        posts_qs = posts_qs.filter(created_at__gte=start_date)
        barters_qs = barters_qs.filter(completed_at__gte=start_date)
    elif period == 'Y':
        start_date = now - timedelta(days=365)
        posts_qs = posts_qs.filter(created_at__gte=start_date)
        barters_qs = barters_qs.filter(completed_at__gte=start_date)

    avg_rating = barters_qs.aggregate(avg=Avg('rating'))['avg'] or 0.0

    return JsonResponse({
        'period': period,
        'rating': round(avg_rating, 1),
        'total_posts': posts_qs.count(),
        'total_barters': barters_qs.count(),
    })


@login_required
@require_GET
def get_posts_json(request):
    """
    Endpoint JSON untuk mengambil list barang dengan dukungan:
    Search, Multi-Filter, Urutkan (Sort), dan Infinite Scrolling (Pagination).
    """
    # Ambil post milik user yang sedang login (atau hapus filter user=... jika ingin katalog publik)
    queryset = Post.objects.filter(user=request.user).annotate(
        user_avg_rating=Avg('user__barter_transactions__rating')
    )

    # 1. Search Bar (cari di judul, deskripsi, atau barang tukaran yang dicari)
    q = request.GET.get('q', '').strip()
    if q:
        queryset = queryset.filter(
            Q(title__icontains=q) | 
            Q(description__icontains=q) | 
            Q(preferred_barter__icontains=q)
        )

    # 2. Filter Samping Kiri (Lokasi, Kondisi, Durasi Pengiriman, Status)
    location = request.GET.get('location', '').strip()
    if location:
        queryset = queryset.filter(location__icontains=location)

    condition = request.GET.get('condition', '').strip()
    if condition:
        queryset = queryset.filter(condition=condition)

    shipping = request.GET.get('shipping', '').strip()
    if shipping:
        queryset = queryset.filter(shipping_duration=shipping)

    status = request.GET.get('status', '').strip()
    if status:
        queryset = queryset.filter(status=status)

    # 3. Urutkan (Terbaru, Terlama, Rating Pengguna)
    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'oldest':
        queryset = queryset.order_by('created_at')
    elif sort_by == 'rating':
        queryset = queryset.order_by('-user_avg_rating', '-created_at')
    else:  # default: newest
        queryset = queryset.order_by('-created_at')

    # 4. Pagination untuk Infinite Scroll (5 item per muatan)
    page_number = int(request.GET.get('page', 1))
    paginator = Paginator(queryset, 5)
    page_obj = paginator.get_page(page_number)

    posts_data = []
    for post in page_obj:
        posts_data.append({
            'id': post.id,
            'title': post.title,
            'description': post.description,
            'image_url': post.image_url or 'https://placehold.co/300x300/e2e8f0/475569?text=Barang',
            'location': post.location,
            'condition_code': post.condition,
            'condition_label': post.get_condition_display(),
            'shipping_code': post.shipping_duration,
            'shipping_label': post.get_shipping_duration_display(),
            'status_code': post.status,
            'status_label': post.get_status_display(),
            'preferred_barter': post.preferred_barter,
            'created_at': post.created_at.strftime('%d %b %Y'),
        })

    return JsonResponse({
        'posts': posts_data,
        'has_next': page_obj.has_next(),
        'current_page': page_obj.number,
    })


@login_required
@require_POST
def create_post_ajax(request):
    """Endpoint AJAX untuk menambah post baru."""
    form = PostForm(request.POST)
    if form.is_valid():
        post = form.save(commit=False)
        post.user = request.user
        if not post.image_url:
            post.image_url = 'https://placehold.co/300x300/e2e8f0/475569?text=Barang'
        post.save()
        return JsonResponse({'status': 'success', 'message': 'Post berhasil ditambahkan!'}, status=201)
    return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


@login_required
@require_POST
def edit_post_ajax(request, post_id):
    """Endpoint AJAX untuk mengedit post yang sudah ada."""
    post = get_object_or_404(Post, id=post_id, user=request.user)
    form = PostForm(request.POST, instance=post)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'success', 'message': 'Post berhasil diperbarui!'})
    return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)


@login_required
@require_POST
def delete_post_ajax(request, post_id):
    """Endpoint AJAX untuk menghapus post."""
    post = get_object_or_404(Post, id=post_id, user=request.user)
    post.delete()
    return JsonResponse({'status': 'success', 'message': 'Post berhasil dihapus!'})