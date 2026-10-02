# Navbar bersama RePair

Navbar dan kerangka situs menjadi tanggung jawab bersama melalui app `core`.
Kerjakan di branch tersendiri `feat/shared-navbar`, berdasarkan `origin/dev`,
agar anggota lain bisa memakai navbar tanpa menunggu seluruh modul akun Noe.
Branch fitur Noe menerima perubahan navbar ini lewat merge lokal. Push branch
dan PR tetap dilakukan oleh Noe sebagai lead.

Worktree navbar yang disiapkan:
`C:\Users\Noe Andrew\PBP\repair-shared-navbar`.

## Konfigurasi proyek

Di `RePair/settings.py`, tambahkan:

```python
INSTALLED_APPS = [
    # Django dan app anggota lain ...
    "core.apps.CoreConfig",
]

TEMPLATES[0]["DIRS"] = [BASE_DIR / "templates"]
TEMPLATES[0]["OPTIONS"]["context_processors"].append(
    "core.context_processors.navigation"
)
STATICFILES_DIRS = [BASE_DIR / "static"]
```

Pastikan context processor bawaan `request`, `auth`, dan `messages` tetap
terdaftar. App `core` tidak memiliki model atau migrasi database.

Di `RePair/urls.py`, pasang `core` sebelum route catch-all:

```python
urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),  # /landing/ bernama core:landing
    # URL app anggota lain ...
]
```

`core:landing` selalu menjadi tujuan tombol Beranda dan memiliki URL
`/landing/`. Pada branch navbar, halaman ini dapat dibuka tanpa login.
Branch akun mengaktifkan autentikasi melalui pengaturan berikut:

```python
LOGIN_URL = "accounts:auth"
LOGIN_REDIRECT_URL = "core:landing"
REQUIRE_LOGIN_FOR_LANDING = True
```

Pengaturan tersebut ditambahkan setelah app `accounts` sudah digabungkan.
Tanpa pengaturan `REQUIRE_LOGIN_FOR_LANDING`, `core` dapat berdiri sendiri.
Tidak ada import langsung dari `core` ke `accounts`.

## Pemakaian oleh anggota tim

Template setiap modul cukup mewarisi `base.html`:

```django
{% extends 'base.html' %}
{% load static %}
{% block title %}Keranjang{% endblock %}
{% block extra_css %}
<link rel="stylesheet" href="{% static 'keranjang/css/keranjang.css' %}">
{% endblock %}
{% block content %}
<section class="panel">
    <h1>Keranjang</h1>
    <!-- Konten app masing-masing. -->
</section>
{% endblock %}
```

Blok bersama: `title`, `navbar`, `main_class`, `content`, `extra_css`, dan
`extra_js`. Navbar, pesan Django, footer, dan CSS situs disediakan oleh base.
CSS modul harus berada dalam app masing-masing dan dimuat lewat `extra_css`.
Halaman autentikasi akun mengganti blok `navbar` dengan header merek minimal.
Halaman profil dan pengaturan memakai navbar utama.

Class bersama yang tersedia: `shell`, `panel`, `panel-heading`, `eyebrow`,
`muted`, `button`, `button-primary`, `button-secondary`, `button-danger`,
`button-row`, `field`, `form-grid`, `account-form`, `form-errors`, `field-error`,
`help-text`, `checkbox-field`, `messages`, dan `message`.

## Integrasi landing milik Aisha

Halaman `core/templates/core/landing.html` saat ini hanya memberi tujuan
setelah login dan menjelaskan bahwa modul utama sedang disiapkan. Tidak ada
barang contoh atau data barter buatan.

Saat modul Aisha siap, pertahankan URL `/landing/` dan nama `core:landing`.
Pindahkan penyajian landing ke view `main_page:show_main` milik Aisha dengan
mount app pada `/landing/`. Cara integrasi yang menjaga nama URL bersama:

```python
# core/urls.py pada PR integrasi main page
from django.urls import path
from main_page.views import show_main

app_name = "core"
urlpatterns = [path("landing/", show_main, name="landing")]

# RePair/urls.py: include core dahulu agar /landing/ memakai view yang sama
path("", include("core.urls")),
path("landing/", include("main_page.urls")),
```

Dengan cara ini `core:landing` dan `main_page:show_main` sama-sama bisa
menunjuk `/landing/` tanpa redirect antarhalaman. View `show_main` perlu
memeriksa login, misalnya dengan `@login_required`, setelah autentikasi
diaktifkan. Root `/` tetap milik entry point autentikasi modul akun.
Jangan memasang app `main_page` pada root `/` atau mengarahkan `core:landing`
kembali ke root karena dapat mengganggu entry point atau membuat loop.

## Nama URL anggota lain

- **Keranjang**: otomatis aktif bila nama route `keranjang` tersedia; nama
  `keranjang:show_keranjang` dan `cart:index` juga dikenali.
- **Post Saya**: otomatis aktif bila route `daftar_post:show_daftar_post`,
  `daftar_post:show_posts`, `posts:my_posts`, atau `post_list:show_posts` tersedia.
- Bila nama route anggota berbeda, set `NAVBAR_CART_URL_NAME` atau
  `NAVBAR_POSTS_URL_NAME` di settings ke nama URL yang benar.
- **Profil & Pengaturan**: memakai `accounts:profile`.
- **Masuk / Daftar**: memakai `accounts:auth` atau alias `accounts:login`.
- **Keluar**: form `POST` ke `accounts:logout`, disertai token CSRF.

Link app yang belum tersedia menjadi teks nonaktif dan tidak memiliki `href`
palsu. Navbar tidak akan menyebabkan `NoReverseMatch` saat app anggota lain
belum digabungkan. Penandaan link aktif memakai URL yang sedang dibuka.

## Pembagian tanggung jawab dan PR

Lead memelihara `core/`, `templates/base.html`,
`templates/components/navbar.html`, dan `static/css/site.css` melalui PR
`feat/shared-navbar` ke `dev`. Anggota memelihara view, URL, template, dan
aset modulnya sendiri. Perubahan menu baru dikoordinasikan lewat lead.

Urutan penggabungan: navbar ke `dev`, modul akun ke `dev`, lalu modul anggota
lain setelah lolos review dan validasi. Jika modul akun sudah membawa merge
branch navbar, PR akun setelah navbar masuk ke `dev` hanya berisi selisih
modul akun. Gunakan merge commit untuk PR navbar supaya sejarah shared branch
dikenali saat PR akun dibandingkan dengan `dev`.

Jalankan pemeriksaan:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test core
```

Tes `core` menggunakan URL uji terpisah untuk memastikan navbar tetap bisa
dirender sebelum maupun setelah app akun, keranjang, dan daftar post tersedia.
