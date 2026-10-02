# RePair

Nama Aplikasi: **RePair**
<br><br>

## Nama & NPM Anggota Kelompok:
1. Aisha Ibnaty Zahira (2506624726)
2. Hafizuddin Dzaki Azzam (2506597220)
3. Naila Salsabila (2506620702)
4. Noe Andrew JM. Silalahi (2506621440)
5. Rasya Azyan Kautsar (2506538981)
<br><br>

## Deskripsi Aplikasi
    RePair merupakan sebuah aplikasi untuk mempertemukan barang-barang bekas yang tidak terpakai dengan pemilik baru yang lebih membutuhkan. Tujuan utama dari aplikasi ini adalah untuk meminimalisir produksi sampah dari barang-barang yang dapat dimanfaatkan kembali. RePair hadir untuk memberikan nilai tambah suatu barang pada tangan orang-orang yang tepat.
<br><br>

## Proses Bisnis utama meliputi
- User membuat akun dan menyertakan media sosial yang dapat dihubungi
- User 1 membuat Post (berisi informasi barang yang ingin diberikan dan didapatkan)
- User 2 melakukan Bid (pengajuan) untuk menukar (berisi pengajuan dan barang atau jasa yang dapat ditawarkan)
- User 1 menyetujui Bid (pengajuan)
- User 1 menghubungi User 2 via aplikasi media sosial (External Business Process)
- User 2 menerima informasi (via Aplikasi)
- User 1 & 2 mencapai kesepakatan
<br><br>

## Unique Selling Point
Pada RePair, seluruh transaksi akan dilaksanakan dalam bentuk barter/sukarela (donasi), sehingga user dapat memilih barang/jasa lainnya sesuai dengan kebutuhan saat itu.
<br><br>

## User Role
User role pada aplikasi ini hanya 1 (tidak termasuk superadmin), jadi setiap orang dapat membuat post dan mengajukan penawaran barter.
<br><br>

## User Persona
Kami menargetkan user utama berupa siswa, mahasiswa, dan pekerja dengan range usia 15 sampai 30 tahun di Kota Depok.
<br><br>

## Kompetitor
1. Aplikasi E-Commerce (Tokopedia, Shopee, Blibli, dan lainnya)
2. Aplikasi Barter Daring (Belum ada aplikasi skala Produksi)
3. Forum Media Sosial (Facebook Marketplace dan lainnya)
<br><br>

## MVP (Minimum Viable Product)
1.  Halaman Login/Register dan Profil & Setting (PIC: Noe Andrew JM. Silalahi)
Pada halaman ini, user dapat melakukan register akun baru, dengan field utama seperti (Nama, akun email, domisili, tanggal lahir, password, dan field lain yang mungkin dibutuhkan). Lalu user juga dapat user dapat melihat detail akun, mengubah password, dan mengubah preferensi penggunaan aplikasi.
a. Create	
    Register	
        Nama, email, domisili, tanggal lahir, password + konfirmasi. Domisili bisa dropdown dari emsifa/api-wilayah-indonesia biar seragam.

b. Read	
    Lihat detail akun	
        Halaman profil, password jangan ditampilkan.

c. Update	
    Edit profil dan ubah password	
        Ubah password minta password lama dulu. Di Django, panggil update_session_auth_hash(request, user) setelah set_password() biar user nggak ke-logout.

d. Delete	
    Hapus akun 	
        soft delete, yaitu set is_active = False sehingga akun cuma dinonaktifkan.


2. Modul Barter / Main Page (PIC: Aisha Ibnaty Zahira)
Pada modul ini, user dapat melihat seluruh barang yang sedang ditawarkan oleh pengguna lainnya, beberapa fitur yang dibutuhkan adalah Search Bar, Halaman Rekomendasi (berisi card barang-barang rekomendasi), Card Barang yang ditawarkan (berisi informasi singkat berupa Foto, Nama Barang, Kondisi Kelayakan, dan Tombol Keranjang), Filter, Tombol & Menu Post Barang

Create: Post Barang Baru, Read: Melihat daftar barang yang ada, Update:-, Delete:-.

3. Modul Detail Barter (PIC: Rasya Azyan Kautsar)
Pada modul ini, user dapat melakukan business process utama untuk menukar barang dengan barang/jasa lainnya, dengan komponen berupa halaman Detail Barang (seperti Foto, Nama, Deskripsi, Kondisi Kelayakan Barang, Barang/Jasa yang ingin didapatkan (opsional), Lokasi Titik Temu, Deadline Penawaran, Tombol Keranjang, dan Tombol Ajukan Penawaran beserta dengan menu pengajuan barang).

Create: Buat penawaran , Read: Lihat data detail barang yang dipilih, Update:- , Delete: Batalkan penawaran.

4. Modul Keranjang (PIC: Hafizuddin Dzaki Azzam)
Pada modul ini, user dapat melihat kembali baarng-barang yang pernah disimpan sebelumnya.

Create: Simpan barang ke keranjang, Read: Lihat barang yang pernah disimpan, Update:- , Delete: Hapus barang dari keranjang.

5. Modul Daftar Post (PIC: Naila Salsabila)
Pada modul ini, user dapat melihat seluruh post yang pernah dibuat, menghapus post, dan melihat siapa saja yang membuat pengajuan dari barang tersebut beserta detail informasi (Nama User, Domisili, dan Barang/Jasa yang dapat ditawarkan)


### Fitur lain yang dapat dibangun (Nice To Have Features)
1. Modul Peta Persebaran Lokasi Service Barang
Dengan Modul ini, user diharapkan akan berpikir dua kali untuk membuang barang-barang yang rusak, selama barang masih dapat digunakan, maka pasti akan ada jalan untuk tidak membuang barang tersebut.

2. Modul Forum
Dengan modul ini, harapannya user bisa berinteraksi dengan user lainnya untuk mencari barang bekas secara khusus sesuai kebutuhan, atau sekadar untuk mengajukan pertanyaan yang berkaitan dengan barang bekas yang dimiliki.
<br><br>

## List API
- OpenStreetMap: Untuk memudahkan pencarian titik temu
- Cloudinary: Upload & kompresi foto barang bekas
- emsifa/api-wilayah-indonesia Standarisasi input domisili kota/kecamatan
- Nominatim (OSM): Konversi titik temu ke nama lokasi
- Firebase Auth & FCM: Login cepat & notifikasi
- Overpass API (OSM): Sumber data lokasi tempat reparasi/servis barang
- Sightengine: Moderasi foto barang otomatis
<br><br>

## Link Proyek
**Link Figma:** https://www.figma.com/design/DECET1J0NLpkkESRoc5YL0/PBP-%7C-Re.Pair?node-id=0-1&t=ETOfeGihmOFiVStt-1

**Link Deployment PWS:** https://pws.cs.ui.ac.id/rasya.azyan/repair

## Modul 1 — Noe Andrew

App Django tersendiri: `accounts`. Modul terdiri dari dua layar utama:

| Layar | URL | Perilaku |
| --- | --- | --- |
| Auth | `/accounts/auth/` | Mode Masuk atau Daftar pada satu halaman; login menggunakan username atau email |
| Profil & Pengaturan | `/accounts/profile/` | Profil, preferensi, ubah password, dan nonaktifkan akun; perlu login |

URL `/` mengarahkan pengunjung ke Auth, dan pengguna yang sudah login ke
`/landing/`. Login atau register yang berhasil langsung membuat sesi lalu
membuka landing. URL lama `/accounts/login/`, `/accounts/register/`, dan
`/accounts/settings/` mengarahkan ke dua layar tersebut.

Field pendaftaran: username, nama lengkap, email, domisili, tanggal lahir,
kontak media sosial opsional, password dan konfirmasi. Password di-hash oleh
Django. Pengaturan hanya mengubah akun pengguna yang login. Ubah password
memerlukan password lama dan mempertahankan sesi pengguna. Nonaktifkan akun
memerlukan password serta konfirmasi, memakai `is_active=False`, lalu logout.
Preferensi tersimpan mencakup notifikasi email, visibilitas profil, dan bahasa;
pengiriman email dan terjemahan antarmuka belum diterapkan.

Navbar bersama berasal dari branch `feat/shared-navbar`, memakai app `core`,
`templates/base.html`, `templates/components/navbar.html`, dan `static/css/site.css`.
Modul lain mewarisi base ini. `/landing/` sekarang berisi halaman penghubung
sementara sampai modul `main_page` milik Aisha digabung; belum ada katalog barter.

Jalankan dengan `PRODUCTION=False` pada environment lokal:

```powershell
$env:PRODUCTION = 'False'
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py runserver
```

Pengujian memakai database SQLite sementara:

```powershell
.\.venv\Scripts\python.exe manage.py test accounts core --settings=accounts.test_settings
```

Panduan [integrasi navbar](docs/NAVBAR_INTEGRATION.md),
[commit modul 1](docs/MODULE_1_WORKFLOW.md), dan
[review/merge PR untuk lead](docs/TEAM_PR_WORKFLOW.md) menjelaskan urutan
navbar → modul fitur → `dev` → `main`. Branch fitur dipertahankan setelah merge.
