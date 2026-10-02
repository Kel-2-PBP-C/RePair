# Alur Git Modul 1

Modul: Login/Register, Profil, dan Setting — PIC Noe Andrew JM. Silalahi.
Branch fitur: `Halaman-Login/Register-dan-Profil-dan-Setting`.

## Commit checkpoint yang sudah dibuat

Jalankan dari folder RePair. Periksa `git diff` sebelum commit:

```powershell
git status
git diff
git add accounts .gitignore README.md RePair/settings.py RePair/urls.py docs/MODULE_1_WORKFLOW.md
git commit -m "feat(accounts): tambah halaman login, register, profil, dan setting"
git push -u origin "Halaman-Login/Register-dan-Profil-dan-Setting"
```

Push dijalankan sendiri oleh Noe. Setelah push, buka PR dengan **base `dev`**
dan **compare `Halaman-Login/Register-dan-Profil-dan-Setting`**, lalu minta
anggota kelompok melakukan review. Merge setelah disetujui dan pertahankan
branch fitur; jangan pilih opsi menghapus branch setelah merge.

## Sebelum mengerjakan perubahan berikutnya

Pastikan pekerjaan lokal sudah di-commit sebelum berpindah branch:

```powershell
git checkout dev
git pull --ff-only origin dev
git checkout "Halaman-Login/Register-dan-Profil-dan-Setting"
git merge dev
```

Jika `dev` lokal belum ada, buat sekali dengan `git checkout -b dev --track origin/dev`.
Checkpoint ini sudah menyinkronkan `dev` dan kembali ke branch fitur.

## Perintah push branch dev

Alur utama tim tetap push branch fitur lalu PR ke `dev`. Jika tim menyiapkan
commit hasil review pada **branch dev lokal**, perintah push-nya adalah:

```powershell
git checkout dev
git push origin dev
```

Jangan memakai perintah ini untuk melewati review PR. Setelah semua modul
tergabung dan sudah diperiksa di `dev`, tim membuka PR `dev` → `main`.
