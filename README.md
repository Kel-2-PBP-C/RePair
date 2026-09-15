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
3. Forum Media Sosial (Facebook dan lainnya)
<br><br>

## MVP (Minimum Viable Product)
1.  Halaman Login/Register (PIC: Noe Andrew JM. Silalahi)
Pada halaman ini, user dapat melakukan register akun baru, dengan field utama seperti (Nama, akun email, domisili, tanggal lahir, password, dan field lain yang mungkin dibutuhkan).

2. Modul Barter (PIC: Rasya Azyan Kautsa)
Pada modul ini, user dapat melakukan business process utama untuk menukar barang dengan barang/jasa lainnya, beberapa fitur yang dibutuhkan adalah Search Bar, Halaman Rekomendasi (berisi card barang-barang rekomendasi), Card Barang yang ditawarkan (berisi informasi singkat berupa Foto, Nama Barang, Kondisi Kelayakan, dan Tombol Keranjang), Menu Detail Barang (seperti Foto, Nama, Deskripsi, Kondisi Kelayakan Barang, Barang/Jasa yang ingin didapatkan (opsional), Lokasi Titik Temu, Deadline Penawaran, Tombol Keranjang, dan Tombol Ajukan Penawaran beserta dengan menu pengajuan barang), Tombol & Menu Post Barang (berisi field untuk menambah informasi barang (Sama seperti yang terdapat pada Menu Detail Barang))

3. Modul Keranjang (PIC: Hafizuddin Dzaki Azzam)
Pada modul ini, user dapat melihat kembali baarng-barang yang pernah disimpan sebelumnya.

4. Modul Daftar Post (PIC: Naila Salsabila)
Pada modul ini, user dapat melihat seluruh post yang pernah dibuat, menghapus post, dan melihat siapa saja yang membuat pengajuan dari barang tersebut beserta detail informasi (Nama User, Domisili, dan Barang/Jasa yang dapat ditawarkan)

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
<br><br>

## Link Proyek
**Link Figma:** https://www.figma.com/design/DECET1J0NLpkkESRoc5YL0/PBP-%7C-Re.Pair?node-id=0-1&t=ETOfeGihmOFiVStt-1
**Link Deployment PWS:** https://pws.cs.ui.ac.id/rasya.azyan/repair
