# Navbar bersama RePair

Navbar dan kerangka situs menjadi tanggung jawab bersama melalui app `core`.
Kerjakan di branch tersendiri `feat/shared-navbar`, berdasarkan `origin/dev`,
agar anggota lain bisa memakai navbar tanpa menunggu seluruh modul akun Noe.
Komponen yang sama sudah dipasang pada proyek utama; sumber komponen bersama
tetap dipelihara di folder `repair-shared-navbar`. Push branch dan PR tetap
dilakukan oleh Noe sebagai lead.

Worktree navbar yang disiapkan:
`C:\Users\Noe Andrew\PBP\re&pair\repair-shared-navbar`.

## Tampilan dan berkas komponen

Lima menu selalu menampilkan ikon dan tulisan **Home, Cart, Forum, Posts,
Settings**. Posisi menyesuaikan lebar layar:

- **HP, di bawah 768 px:** navbar putih tetap di bawah dengan sudut atas
  membulat. Ikon dan label menu aktif berwarna hijau.
- **Laptop, mulai 768 px:** navbar hijau tetap di atas, logo RePair di kiri,
  lalu lima ikon dan label. Ikon dan label menu aktif berwarna putih.

Tombol keluar tidak ada di navbar. **Keluar dari Akun** berada di halaman
Settings dan memakai form POST ke `accounts:logout` dengan token CSRF.

Berkas komponen berada di `templates/components/navbar.html`,
`static/css/navbar.css`, `core/context_processors.py`, dan `static/img/`.
`templates/base.html` memuat `css/navbar.css` sesudah `css/site.css`.
CSS navbar memakai awalan class `repair-navbar-` agar terpisah dari CSS modul.
Logo memakai `Group 40.png`, latar desktop memakai `Group 46.png`, dan lima
ikon memakai `home_filled.png`, `shopping_cart.png`,
`chat_bubble_outline.png`, `insert_photo.png`, serta `settings.png`.

Body base memakai `has-responsive-navbar`. Class ini menyediakan ruang 96 px
di atas pada laptop atau 84 px ditambah safe area perangkat di bawah pada HP,
agar konten dan footer tidak tertutup navbar. Jika template menambah class body,
pertahankan class tersebut:

```django
{% block body_class %}has-responsive-navbar halaman-modul{% endblock %}
```

Saat mengintegrasikan revisi, bawa stylesheet navbar dan seluruh asetnya bersama
template, base, serta context processor. Perbarui sumber di `repair-shared-navbar`
dan salin komponen yang sama ke proyek utama; proyek utama tidak mengimpor
template atau aset melalui path folder worktree.

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

`core:landing` selalu menjadi tujuan menu Home dan memiliki URL
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

Blok bersama: `title`, `body_class`, `navbar`, `main_class`, `content`, `extra_css`, dan
`extra_js`. Navbar, pesan Django, footer, dan CSS situs disediakan oleh base.
CSS modul harus berada dalam app masing-masing dan dimuat lewat `extra_css`.
Landing publik, autentikasi Google, kredensial, dan onboarding akun memakai
`accounts/brand_base.html` tanpa navbar aplikasi. Halaman profil dan pengaturan
memakai navbar utama. Template yang sengaja mengganti blok `navbar` tanpa
menampilkan navbar juga perlu mengganti `body_class` agar ruang navbar tidak
ditambahkan.

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

- **Home**: memakai `core:landing` (`/landing/`).
- **Cart**: otomatis aktif bila nama route `keranjang` tersedia; nama
  `keranjang:show_keranjang` dan `cart:index` juga dikenali.
- **Forum**: otomatis aktif bila route `forum:show_forum`, `forum:index`,
  `forum:forum_list`, atau `forum:home` tersedia.
- **Posts**: otomatis aktif bila route `daftar_post:show_daftar_post`,
  `daftar_post:show_posts`, `posts:my_posts`, `post_list:show_posts`, atau
  `profile_post:show_profile` tersedia.
- Bila nama route anggota berbeda, set `NAVBAR_CART_URL_NAME`,
  `NAVBAR_FORUM_URL_NAME`, atau `NAVBAR_POSTS_URL_NAME` di settings ke nama URL
  yang benar.
- **Settings**: memakai `accounts:profile` untuk pengguna yang login;
  `accounts:profile` dan `accounts:settings` sama-sama mengaktifkan menu Settings.
  Untuk tamu, menu ini menuju `accounts:auth` atau alias `accounts:login`.

Menu app yang belum tersedia tetap menampilkan ikon dan label nonaktif dengan
`aria-disabled="true"`, tanpa `href` palsu. Navbar tidak akan menyebabkan
`NoReverseMatch` saat app anggota lain belum digabungkan. Penandaan menu aktif
memakai URL yang sedang dibuka, termasuk halaman turunan seperti topik forum.

## Pembagian tanggung jawab dan PR

Lead memelihara `core/`, `templates/base.html`,
`templates/components/navbar.html`, `static/css/navbar.css`, aset navbar di
`static/img`, dan kerangka `static/css/site.css` melalui PR
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
.\.venv\Scripts\python.exe manage.py test core --settings=accounts.test_settings
```

Perintah test di atas untuk proyek utama dan memakai database sementara.
Di worktree standalone, jalankan `..\.venv\Scripts\python.exe manage.py test core`;
app akun tidak diperlukan untuk pengujian komponen navbar.

Tes navbar menggunakan URL uji terpisah untuk memastikan komponen tetap bisa
dirender sebelum maupun setelah app akun, keranjang, forum, dan daftar post
tersedia. Validasi browser juga memeriksa lima ikon dan label, posisi navbar
di bawah/atas pada batas 768 px, serta konten dan footer yang tidak tertutup.
