# Re&Pair

Nama Aplikasi: **Re&Pair**
<br><br>

## Nama & NPM Anggota Kelompok:
1. Aisha Ibnaty Zahira (2506624726)
2. Hafizuddin Dzaki Azzam (2506597220)
3. Naila Salsabila (2506620702)
4. Noe Andrew JM. Silalahi (2506621440)
5. Rasya Azyan Kautsar (2506538981)
<br><br>

## Deskripsi Aplikasi
    Re&Pair merupakan sebuah aplikasi untuk mempertemukan barang-barang bekas yang tidak terpakai dengan pemilik baru yang lebih membutuhkan. Tujuan utama dari aplikasi ini adalah untuk meminimalisir produksi sampah dari barang-barang yang dapat dimanfaatkan kembali. Re&Pair hadir untuk memberikan nilai tambah suatu barang pada tangan orang-orang yang tepat.
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
Pada Re&Pair, seluruh transaksi akan dilaksanakan dalam bentuk barter/sukarela (donasi), sehingga user dapat memilih barang/jasa lainnya sesuai dengan kebutuhan saat itu.
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
Modul ini menangani pendaftaran, login, profil, dan pengaturan akun. Fitur yang sudah selesai dikerjakan:

a. Create
    Register dan login Google
    - Pendaftaran dan verifikasi identitas menggunakan akun Google.
    - Pengguna baru membuat username unik dan password RePair setelah verifikasi Google.
    - Pengguna lama masuk melalui Google, lalu memverifikasi username dan password RePair.
    - Akun lama dapat ditautkan ke Google setelah verifikasi Google dan kredensial akun lama.
    - Halaman Lengkapi Profil ditampilkan setelah login, dengan pilihan Simpan & Lanjutkan atau Lewati Dulu.

b. Read
    Lihat profil dan informasi aplikasi
    - Menampilkan nama, email Google, username, lokasi, dan kategori barang pilihan pada profil.
    - Menyediakan landing page, halaman kredensial, Lengkapi Profil, Settings, Syarat & Ketentuan, dan Kebijakan Privasi.
    - Halaman syarat dan privasi dapat diakses tanpa login.
    - Password disimpan dalam bentuk hash dan tidak ditampilkan pada profil.

c. Update
    Edit profil, preferensi, dan password
    - Mengubah username, nama, lokasi, tanggal lahir, dan kontak media sosial. Email Google tidak dapat diubah melalui form profil.
    - Memilih kota/kabupaten dari dropdown pencarian BogorTech atau mengetik lokasi secara manual. Pilihan API menyimpan kode wilayah dan nama daerah beserta provinsinya.
    - Mengubah kategori barang pilihan, preferensi notifikasi email, visibilitas profil, dan bahasa aplikasi. Pengiriman email dan terjemahan antarmuka belum diterapkan.
    - Mengubah password dengan memasukkan password lama; sesi login tetap dipertahankan setelah perubahan.
    - Tombol Edit Profil, Simpan Profil, dan Batal tersedia pada Settings.

d. Delete
    Hapus akun dan keluar
    - Menghapus akun secara permanen beserta profil, identitas Google, postingan barang, dan sesi login terkait.
    - Penghapusan memerlukan password RePair dan konfirmasi; akun tanpa password RePair menggunakan verifikasi ulang Google.
    - Pengguna keluar dari semua perangkat, kembali ke landing page, dan menerima notifikasi penghapusan.
    - Email dan akun Google yang sama dapat dipakai untuk mendaftar kembali.
    - Tombol Keluar dari Akun tersedia di Settings.

Tampilan landing, login, Lengkapi Profil, dan Settings menyesuaikan layar HP dan laptop. Navbar bersama menampilkan Home, Cart, Forum, Posts, dan Settings; berada di bawah pada HP dan di atas pada laptop.


2. Modul Barter / Main Page (PIC: Aisha Ibnaty Zahira)
Pada modul ini, user dapat melihat seluruh barang yang sedang ditawarkan oleh pengguna lainnya, beberapa fitur yang dibutuhkan adalah Search Bar, Halaman Rekomendasi (berisi card barang-barang rekomendasi), Card Barang yang ditawarkan (berisi informasi singkat berupa Foto, Nama Barang, Kondisi Kelayakan, dan Tombol Keranjang), Filter, Tombol & Menu Post Barang

Create: Post Barang Baru, Read: Melihat daftar barang yang ada, Update: Menyediakan tombol edit barang, Delete: Menyediakan tombol untuk hapus barang pengguna.

### Detail CRUD – Main Page

1. Create
- Menyediakan tombol Post Barang pada halaman utama yang mengarahkan pengguna ke halaman pembuatan barang baru pada modul Daftar Post.
- Barang yang berhasil ditambahkan akan ditampilkan secara dinamis pada Main Page.

2. Read
- Menampilkan daftar barang yang tersedia berdasarkan data dari database.
- Menampilkan informasi barang berupa foto, nama barang, tahun barang, kondisi kelayakan, lokasi, dan barang yang diinginkan sebagai pengganti.
- Menyediakan fitur pencarian barang berdasarkan nama.
- Menyediakan filter berdasarkan kondisi barang, yaitu Baru, Bekas – Layak Pakai, dan Butuh Perbaikan.

3. Update
- Menyediakan tombol Edit Barang untuk mengarahkan pengguna ke halaman pengeditan barang pada modul Daftar Post.
- Tombol edit hanya ditampilkan untuk barang milik pengguna yang sedang login.
- Perubahan informasi barang akan ditampilkan kembali pada Main Page.

4. Delete
- Menyediakan tombol Hapus Barang untuk menghapus barang milik pengguna melalui integrasi dengan modul Daftar Post.
- Tombol hapus hanya ditampilkan untuk barang milik pengguna yang sedang login.
- Setelah penghapusan berhasil, barang tidak lagi ditampilkan pada daftar Main Page.

### AI Disclosure – Main Page

    1. Tools
    - ChatGPT (web)

    2. Prompt Strategy
    - Menentukan kebutuhan fitur Main Page terlebih dahulu, seperti menampilkan daftar barang, fitur pencarian, filter kondisi barang, serta tampilan card barang sesuai desain Figma.
    - Menggunakan AI untuk membantu memahami implementasi Django, terutama dalam mengambil dan menampilkan data barang secara dinamis dari database.
    - Memanfaatkan AI untuk memberikan arahan dalam menghubungkan tombol pada Main Page dengan fitur dari modul lain, seperti tambah barang, edit barang, hapus barang, dan keranjang.
    - Menggunakan AI untuk membantu proses debugging ketika terjadi error pada implementasi maupun integrasi antarmodul.
    - Memanfaatkan AI untuk membantu menyusun unit test, kemudian menjalankan pengujian dan memeriksa hasilnya secara langsung.
    - Melakukan penyesuaian kode dan tampilan berdasarkan hasil pengujian agar fitur Main Page berjalan sesuai kebutuhan.

    3. Prompting Log
    - Perancangan dan penyesuaian tampilan Main Page berdasarkan desain Figma.
    - Implementasi fitur pencarian dan filter kondisi barang.
    - Integrasi fitur CRUD Main Page dengan modul lain.
    - Debugging integrasi tombol Add to Cart dengan modul Keranjang.
    - Pembuatan dan pengujian unit test Main Page.
    - Seluruh proses dilakukan melalui percakapan ChatGPT selama pengembangan modul.

3. Modul Detail Barter (PIC: Rasya Azyan Kautsar)
Pada modul ini, user dapat melakukan business process utama untuk menukar barang dengan barang/jasa lainnya, dengan komponen berupa halaman Detail Barang (seperti Foto, Nama, Deskripsi, Kondisi Kelayakan Barang, Barang/Jasa yang ingin didapatkan (opsional), Lokasi Titik Temu, Deadline Penawaran, Tombol Keranjang, dan Tombol Ajukan Penawaran beserta dengan menu pengajuan barang).

Create: Buat penawaran , Read: Lihat data detail barang yang dipilih, Update:- , Delete: Batalkan penawaran.

4. Modul Keranjang (PIC: Naila Salsabila)
Pada modul ini, user dapat melihat kembali baarng-barang yang pernah disimpan sebelumnya.

Create: Simpan barang ke keranjang, Read: Lihat barang yang pernah disimpan, Update:- , Delete: Hapus barang dari keranjang.

5. Modul Daftar Post (PIC: Hafizuddin Dzaki Azzam)
Pada modul ini, user dapat melihat seluruh post yang pernah dibuat, menghapus post, dan melihat siapa saja yang membuat pengajuan dari barang tersebut beserta detail informasi (Nama User, Domisili, dan Barang yang  ditawarkan)
    1. Alur Pengguna
        <ul>
            <li>User menambahkan post barter dengan menekan tombol "tambah" di bagian bawah layar.</li>
            <li>Post baru akan terbuat dengan status dasar post "tersedia" dan opsi untuk mengubah informasi barang serta menghapus post.</li>
            <li>User dapat memfilter display post berdasarkan lokasi, status, dan kondisi barang.</li>
            <li>User dapat mengurutkan  display post berdasarkan post terlama, terbaru, dan tawaran terbanyak.</li>
            <li>Apabila suatu post sudah terdapat penawar, user dapat memilih penawar untuk mengunci item barter dengan penawar tersebut, mengubah status barang menjadi "dalam negosiasi".</li>
            <li>Status "dalam negosiasi" dapat dibatalkan atau diubah dengan siapa barter akan dilakukan.</li>
            <li>Apabila user sudah mencapai melakukan barter dengan penawar, user dapat memperbarui status post menjadi selesai (dibarter) dengan menekan tombol "selesaikan".</li>
        </ul>
    2. Detail CRUD
        1. Create
            <ul>
                <li>Menambahkan barang barter dengan informasi nama, deskripsi, lokasi, barang yang diharapkan, kondisi barang, kategori barang, dan url foto barang (opsional).</li>
            </ul>        
        2. Update
            <ul>
                <li>Update detail barang barter meliputi informasi nama, deskripsi, lokasi, barang yang diharapkan, kondisi barang, kategori barang, dan url foto barang (opsional).</li>
                <li>Melakukan perubahan pada pilihan pihak kedua barter.</li>
            </ul>
        3. Read
            <ul>
                <li>Membaca data list barang barter user dari database.</li>
                <li>Membaca data user yang mengajukan tawaran barter pada barang.</li>
                <li>Fitur filter status barter, kondisi barang, lokasi barang dan fitur urutkan post berdasarkan terlama, terbaru, dan tawaran terbanyak.</li>
            </ul>
        4. Delete
            <ul>
                <li>Menghapus barang yang belum dibarter.</li>
                <li>Barang yang sudah dibarter tidak dapat dihapus supaya data review user tetap dapat dipertahankan.</li>
            </ul>
    3. AI Disclosure
        1. Tools
            <ul>
                <li>Gemini 4 Argon (web)</li>
                <li>Claude Sonnet 5.5 (web)</li>
                <li>GPT-6 Luna (VS Code)</li>
            </ul>
        2. Prompt Strategy
            <ul>
                <li>Merancang keseluruhan alur modul serta komponen-komponen yang hendak dibuat terlebih dahulu kemudian menggunakan AI untuk membantu merealisasikan pondasi dari modul.</li>
                <li>Integrasi antar perbaikan yang diberikan oleh AI dilakukan secara manual.</li>
                <li>Bug Fixing bersifat detail kecil (salah satu poin terbesarnya pada bug karena hierarchy CSS) diselesaikan dengan bantuan AI supaya pengembangan dapat berfokus ke scope yang lebih besar.  </li>
            </ul>
        3. Prompting Log
            1. Membentuk struktur proyek: https://share.gemini.google/DpZbZ8UDxCgI
            2. Menambah toast: https://share.gemini.google/lfVTLD3xBQXU
            3. Memperbaiki UI: https://claude.ai/share/56659c6d-aa10-4961-b9fb-f088c00cd4ee
            4. Bug fixing: GPT-6 Luna (dalam session VS Code)

5. Modul Profil & Setting (PIC: Aisha Ibnaty Zahira)
Dalam modul ini, user dapat melihat detail akun, mengubah password, dan mengubah preferensi penggunaan aplikasi

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
- Google OAuth 2.0 / OpenID Connect (Baru): Autentikasi akun Google untuk pendaftaran dan login RePair
- BogorTech API Wilayah Indonesia (Baru): Pencarian kota/kabupaten beserta provinsi dan kode wilayah untuk domisili pengguna
<br><br>

## Link Proyek
**Link Figma:** https://www.figma.com/design/DECET1J0NLpkkESRoc5YL0/PBP-%7C-Re.Pair?node-id=0-1&t=ETOfeGihmOFiVStt-1

**Link Deployment PWS:** https://pws.cs.ui.ac.id/rasya.azyan/repair
