# Pengujian dan coverage

Branch: `Halaman-Login/Register-dan-Profil-dan-Setting`.

## Memeriksa target 90%

Jalankan dari folder yang berisi `manage.py`. Perintah berikut memakai Python
virtual environment proyek, sehingga tidak perlu aktivasi terlebih dahulu.

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-test.txt
.venv/Scripts/python.exe -m coverage run manage.py test accounts core barter_details keranjang main_page profile_post RePair scripts --settings=accounts.test_settings --noinput
.venv/Scripts/python.exe -m coverage report
```

Pastikan hasil test adalah **OK**, lalu lihat kolom **Cover** pada baris
**TOTAL**. `.coveragerc` menetapkan `fail_under = 90`; `coverage report` akan
mengembalikan exit code 1 bila hasilnya di bawah 90%.
Di PowerShell, cek `$LASTEXITCODE` segera setelah perintah tersebut.

Di Linux/macOS atau virtual environment yang sudah aktif, ganti
`.venv/Scripts/python.exe` dengan `python`.

Untuk melihat satu app saja:

```powershell
.venv/Scripts/python.exe -m coverage report --include="accounts/*" --fail-under=90
```

## Laporan visual

```powershell
.venv/Scripts/python.exe -m coverage html
.venv/Scripts/python.exe -m coverage xml
```

Buka `htmlcov/index.html` di browser. Klik nama file untuk melihat baris yang
sudah dijalankan, baris terlewat, dan percabangan yang belum tercakup.
Laporan merupakan artefak lokal yang diabaikan Git dan dapat dibuat ulang.

Hasil verifikasi lokal 30 Oktober 2026: **364 test Python dan 2 test Selenium
lulus**, dengan coverage gabungan suite Python **99,95%** (1.539/1.539 statement
dan 437/438 branch).

| App/folder Python | Coverage statement + branch |
| --- | ---: |
| accounts | 99,93% |
| core | 100,00% |
| barter_details | 100,00% |
| keranjang | 100,00% |
| main_page | 100,00% |
| profile_post | 100,00% |
| RePair | 100,00% |
| scripts | 100,00% |

Angka ini mencakup semua modul Python di delapan folder tersebut, termasuk
model, form, view, middleware, konfigurasi deployment, command, dan pengaman
Git. File test dan migrasi dikecualikan. Persentase tidak mengukur CSS, HTML,
JavaScript, dependency pihak ketiga, atau fitur dari branch lain. Beberapa app
pada branch ini masih berupa halaman sederhana; coverage hanya mengukur kode
yang memang ada pada branch ini.

## Functional testing dengan Selenium

Install Google Chrome, kemudian jalankan:

```powershell
.venv/Scripts/python.exe manage.py test functional_tests --settings=accounts.test_settings --noinput
```

Selenium menjalankan Chrome headless pada server Django dan database test
sementara. Selenium Manager mencari/mengunduh driver yang sesuai saat pertama
digunakan. Bila sudah memiliki driver, set `CHROMEDRIVER` ke path executable;
gunakan `CHROME_BINARY` bila lokasi Chrome tidak standar.

Dua test menguji pendaftaran melalui Google, pembuatan kredensial, onboarding,
edit/batal profil, preferensi, ganti password, logout/login, penghapusan akun,
serta penolakan password dan username salah pada ukuran layar HP. Google dan
API wilayah di-mock di batas layanan eksternal; browser tetap menjalankan
template, JavaScript, CSRF, cookie, form, session, dan penyimpanan database.
Validasi OIDC juga diuji terpisah dengan token bertanda tangan dalam unit test.

Semua test memakai `accounts.test_settings`: SQLite sementara, email dalam
memori, cache lokal, dan kredensial test. Database pengguna tidak digunakan.
Test pengaman Git membuat repository sementara sendiri.

## GitHub Actions

Workflow `.github/workflows/tests.yml` menjalankan suite Python, mewajibkan
coverage minimal 90% secara total **dan per app**, menjalankan Selenium dalam
job terpisah, serta menyimpan laporan HTML/XML/JSON sebagai artifact
`coverage-reports`. Workflow aktif pada push branch ini, `main`, `dev`, dan PR.

Test ini membuktikan perilaku dan coverage saat dijalankan. Riwayat TDD
Red–Green–Refactor tidak diklaim hanya berdasarkan persentase coverage.
