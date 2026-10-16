# Commit dua branch RePair tanpa mengirim .env

Diperbarui: 16 Oktober 2026. Panduan ini untuk PowerShell di VS Code. Perubahan
source sudah disiapkan; commit, push, dan penggabungan PR dilakukan melalui
langkah di bawah. Jangan salin isi `.env` ke terminal, chat, atau GitHub.

## Pembagian kode

| Branch | Isi PR ke `dev` |
| --- | --- |
| `feat/shared-navbar` | Navbar responsif, lima ikon, logo/latar navbar, base template, CSS situs bersama, context processor, test navbar, dokumentasi integrasi dan pengaman Git |
| `Halaman-Login/Register-dan-Profil-dan-Setting` | Google auth, credentials, onboarding/lokasi, Settings, penghapusan akun, halaman publik/kebijakan, migrasi, dependency, konfigurasi backend dan dokumentasi akun |

Branch akun sudah memakai salinan komponen navbar. Commit akun mencatat integrasi
tersebut juga. Setelah PR navbar digabung ke `dev`, merge `origin/dev` ke branch
akun sebelum membuka PR akun. Dengan demikian, selisih **Files changed** PR akun
berisi fitur akun dan integrasinya; navbar yang sama sudah menjadi bagian `dev`.

## 1. Siapkan kedua folder dan aktifkan pengaman

Di VS Code klik **Terminal → New Terminal**, pilih PowerShell, lalu jalankan:

```powershell
Set-Location 'C:\Users\Noe Andrew\PBP\re&pair'
git worktree repair .\repair-shared-navbar .\repair-main-page .\repair-profile-post .\repair-keranjang
git worktree list
git config --local core.hooksPath 'C:/Users/Noe Andrew/PBP/re&pair/.githooks'
git config --get core.hooksPath
git check-ignore -v -- .env
git ls-files -- .env
```

Perbaikan worktree memperbarui lokasi checkout yang pernah dipindah; file source
dan `.env` tidak dihapus. Dua folder yang dipakai di panduan ini:

- Folder utama: branch `Halaman-Login/Register-dan-Profil-dan-Setting`.
- Folder `repair-shared-navbar`: branch `feat/shared-navbar`.

`git check-ignore` harus menunjuk pola `.env*` dari `.gitignore`.
`git ls-files -- .env` harus **tidak menghasilkan output**. Jika `.env` masih
muncul, hentikan proses; untrack dahulu dengan `git rm --cached -- .env` dan
periksa apakah secret pernah ter-commit sebelum melanjutkan. Perintah tersebut
menghapus pencatatan Git, bukan file lokal. Secret yang sudah terkirim ke remote
perlu diganti melalui penyedianya; `.gitignore` tidak membersihkan riwayat lama.

Pengaman lokal memeriksa nama file dan pola rahasia saat commit, serta commit
yang hendak dikirim saat push. `.env` tetap ditolak meskipun dimasukkan dengan
`git add -f`. `.env.example` boleh masuk karena merupakan template konfigurasi;
biarkan nilai rahasianya kosong. Jangan menonaktifkan hook atau memakai
`--no-verify`. Jika clone/folder dipindah lagi, aktifkan ulang `core.hooksPath`
dengan lokasi absolut baru. Hook ini harus diaktifkan sendiri pada clone anggota
tim lain; konfigurasi Git lokal tidak ikut dikirim.

## 2. Commit dan push navbar dahulu

Masih pada terminal yang sama:

```powershell
Set-Location 'C:\Users\Noe Andrew\PBP\re&pair\repair-shared-navbar'
git branch --show-current
git fetch origin
git status --short
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stage_feature.ps1 -Feature Navbar
git --no-pager diff --cached --name-only
```

Branch harus `feat/shared-navbar`. Script hanya men-stage daftar berkas navbar
dan pengaman; script tidak commit atau push. Daftar tidak boleh berisi `accounts/`,
`.env`, database, `.test-artifacts`, atau folder `repair-*` sebagai isi commit.

Jalankan test komponen terpisah dan commit:

```powershell
..\.venv\Scripts\python.exe manage.py test core
git commit -m "feat(navbar): add responsive shared navigation"
..\.venv\Scripts\python.exe scripts\check_git_safety.py --head
git push -u origin feat/shared-navbar
```

Jika fetch/push meminta login, gunakan login GitHub milikmu melalui Git Credential
Manager. Jangan memasukkan Client Secret Google sebagai password Git. Jika push
ditolak **non-fast-forward**, hentikan dan periksa perubahan remote; jangan memakai
`--force`. Jangan lanjut jika test atau pengaman gagal.

## 3. Gabungkan PR navbar ke dev

1. Buka repository [Kel-2-PBP-C/RePair](https://github.com/Kel-2-PBP-C/RePair).
2. Klik **Pull requests → New pull request**.
3. Atur **base: `dev`**, **compare: `feat/shared-navbar`**.
4. Buka tab **Files changed**. Pastikan berkasnya navbar/kerangka bersama,
   aset, test, dokumentasi dan pengaman; tidak ada `.env` atau fitur akun.
5. Klik **Create pull request**. Judul: `feat(navbar): responsive shared navigation`.
6. Setelah review/check lulus, pilih **Create a merge commit → Merge pull request
   → Confirm merge**, bila diizinkan pengaturan repository.

Gunakan merge commit agar riwayat shared branch dikenali saat branch akun
diintegrasikan. Jangan hapus branch navbar dahulu. Ini menggabungkan perubahan
ke `dev`; tidak perlu `git push origin dev` dari branch fitur.

## 4. Commit akun, lalu sinkronkan dengan dev

Kembali ke folder utama melalui terminal:

```powershell
Set-Location 'C:\Users\Noe Andrew\PBP\re&pair'
git branch --show-current
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stage_feature.ps1 -Feature Accounts
git --no-pager diff --cached --name-only
.\.venv\Scripts\python.exe manage.py test --settings=accounts.test_settings --noinput
git commit -m "feat(accounts): add Google auth and profile settings"
git status --short
```

Branch harus `Halaman-Login/Register-dan-Profil-dan-Setting`. `.env.example` adalah
template yang boleh muncul; **`.env` tidak boleh muncul**. Script tidak men-stage
folder checkout tim atau seluruh `static/img` tanpa memilih asetnya. Perubahan
bersama yang sudah dipakai aplikasi ikut dicatat sebagai integrasi.

Setelah status bersih dan PR navbar sudah digabung, jalankan:

```powershell
git fetch origin
git merge --no-edit origin/dev
git status --short
.\.venv\Scripts\python.exe manage.py test --settings=accounts.test_settings --noinput
.\.venv\Scripts\python.exe scripts\check_git_safety.py --head
git push -u origin Halaman-Login/Register-dan-Profil-dan-Setting
```

Jika tidak ada commit baru yang masuk dari `dev`, tidak perlu mengulang test yang
sama setelah merge. Jika status setelah commit masih menunjukkan perubahan,
tinjau berkas yang tersisa sebelum merge; jangan menghapusnya agar status bersih.

Jika merge menampilkan **CONFLICT**, jangan push. Buka **Source Control → Merge
Changes**, tinjau tiap konflik, pertahankan fungsi kedua fitur, lalu stage hanya
file yang telah diselesaikan dan jalankan `git merge --continue`. Ulangi test dan
pengaman sesudahnya. Jangan memilih **Accept All Incoming** untuk seluruh proyek.
Untuk kembali ke keadaan sebelum merge yang dimulai dari status bersih, gunakan
`git merge --abort`; commit fitur tetap ada.

## 5. Gabungkan PR akun ke dev

1. Di GitHub, klik **Pull requests → New pull request**.
2. Atur **base: `dev`**, **compare:
   `Halaman-Login/Register-dan-Profil-dan-Setting`**.
3. Tinjau **Files changed**. Perubahan navbar identik yang sudah masuk `dev`
   tidak seharusnya muncul lagi. `.env`, database dan folder checkout tidak boleh ada.
4. Klik **Create pull request**. Judul: `feat(accounts): Google auth and profile settings`.
5. Setelah review/check lulus, klik **Merge pull request → Confirm merge**.

Kini kedua fitur sudah masuk `dev`. Langkah `dev → main → PWS` dikerjakan setelah
review integrasi tim; panduan ini belum melakukan deployment.

## Jika pengaman menolak commit atau push

Pesan pengaman hanya menyebut nama berkas dan alasan. Untuk mengeluarkan file
dari staging tanpa menghapus file lokal, gunakan nama file yang disebut:

```powershell
git restore --staged -- .env
```

Untuk file lain, ganti `.env` dengan path yang ditolak. Jika ada secret di dalam
source, pindahkan nilainya ke `.env` lokal, baca melalui environment, lalu stage
source yang sudah dibersihkan. Jika pengaman push menemukan `.env` pada commit
lokal, jangan bypass hook: unstage saja tidak menghapus commit lama. Periksa
riwayat dan susun ulang commit lokal tersebut sebelum push.

## Referensi

- [Membuat pull request — GitHub](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request)
- [Menggabungkan pull request — GitHub](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/merging-a-pull-request)
- [gitignore — Git](https://git-scm.com/docs/gitignore)
