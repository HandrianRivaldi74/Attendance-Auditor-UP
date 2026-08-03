# Pemeriksa Absensi & Struk Gaji

## Cara jalankan
```
pip install -r requirements.txt
python app.py
```

## Alur pemakaian
1. **Buka PDF Absensi** -> aplikasi otomatis jalankan Aturan 1-4 (cek anomali) + baca HKP/IJIN/DIRUMAHKAN yang dilaporkan sistem, tampil di tab "Anomali Absensi".
2. **Buka PDF Struk Gaji** -> aplikasi parse data upah per karyawan.
3. **Bandingkan** -> cocokkan kedua dokumen per NRP, tampil di tab "Banding Absensi vs Struk Gaji" dengan status:
   - `COCOK` - HKP, IJIN, DIRUMAHKAN, dan jam LEMBURAN sinkron antara absensi dan struk gaji
   - `TIDAK SINKRON` - ada atribut yang beda (detail perbedaan ditampilkan)
   - `HANYA DI ABSENSI` / `HANYA DI STRUK GAJI` - NRP hanya muncul di salah satu dokumen
4. **Ekspor ke Excel** -> simpan semua hasil (3 sheet: Anomali Absensi, Banding, Ringkasan).

Parser sama (`absensi_parser.py`, `gaji_parser.py`) dipakai untuk KEDUA versi dokumen -
versi otomatis (NON SHIFT/GROUP, periode 26-25, batas HKP 21/25) maupun versi SIPIL/tidak
otomatis (periode setengah bulan, HKP dihitung murni dari kehadiran) - layout PDF-nya
sama persis, cuma isi group & rumus HKP yang beda, jadi tidak perlu parser terpisah.

## Rumus HKP - dua versi (rules.py)
- **Otomatis** (group NON SHIFT 1/2/3, GROUP 1/2/3 PROCESSING, dll): batas group (21
  hari untuk NS1/NS2/GROUP1/GROUP2, 25 hari untuk NS3/GROUP3/SIPIL long-period lama)
  dikurangi hari S2/CI, dikurangi hari DR, dikurangi hari izin lain.
- **SIPIL / tidak otomatis** (group diawali kata "SIPIL", mis. "SIPIL", "SIPIL 2"):
  TIDAK pakai batas 21/25 - HKP dihitung murni dari total kehadiran (jumlah faktor
  "Hari Kerja" harian) dalam periode dokumen. Kalau dalam periode cuma masuk 1x,
  HKP-nya cuma 1. Periode dokumen SIPIL biasanya setengah bulan (mis. 1-15 atau
  16-akhir bulan), beda dari versi otomatis yang periodenya 26-25 sebulan penuh.
  Terdeteksi otomatis dari nama group (`rules._is_sipil()`), jadi satu aplikasi bisa
  memeriksa kedua jenis dokumen tanpa perlu pengaturan manual.

## Status validasi (sudah diuji dengan SEMUA dokumen ASLI yang diberikan)

### Versi otomatis (report_struk_gaji_all.pdf + report_laporan_rekap_absensi_hkp_otomatis__2_.pdf, periode 26/06-25/07/2026)
- `gaji_parser.py` - cocok 100% (66 karyawan, semua subtotal per bagian pas dengan TOTAL tercetak)
- `absensi_parser.py` - 68 karyawan terbaca, HKP/IJIN/DIRUMAHKAN/LEMBURAN sistem cocok 100%
  dengan struk gaji KECUALI SUMARDI (NRP 2312233) - lihat temuan di bawah
- Banding dua dokumen: **65 cocok, 1 tidak sinkron (SUMARDI), 2 hanya di absensi**
  (2 Wakil Direktur berupah 0, wajar tidak ada di struk gaji)
- Aturan 1, 2, 4 - nol false-positive; Aturan 4 otomatis mendeteksi kode '?' milik SUMARDI
- Aturan 3 (rumus HKP manual versi otomatis) - masih ada ~20 selisih kecil dibanding HKP
  resmi sistem (kemungkinan kode DT/CT butuh penanganan pecahan hari yang belum tertangkap
  rumusnya) - TIDAK mengganggu fitur banding dua dokumen karena itu pakai nilai HKP hasil
  laporan sistem, bukan hasil hitung ulang manual

### Versi SIPIL / tidak otomatis (report_struk_gaji.pdf + report_laporan_rekap_absensi.pdf, periode 01/07-15/07/2026)
- `gaji_parser.py` - cocok 100% (30 karyawan, total HKP/IJIN/DIRUMAHKAN/LEMBURAN/U.BERSIH
  pas persis dengan GRAND TOTAL tercetak)
- `absensi_parser.py` - 30 karyawan terbaca, semua field sistem terbaca dengan benar
- Banding dua dokumen: **30 cocok, 0 tidak sinkron** - sinkron sempurna
- Aturan 1-4 - **nol anomali** setelah rumus HKP SIPIL ditambahkan (rumus batas 21/25
  otomatis TIDAK berlaku untuk SIPIL - sudah dipisah di `rules.hitung_hkp_sipil()`)

## Temuan nyata dari data yang diuji
**SUMARDI (NRP 2312233, versi otomatis)** - HKP di absensi = 24, di struk gaji = 23
(selisih karena kode izin '?' di tanggal 30 tidak ikut dikurangi saat sistem menghitung
HKP-nya). Jumlah IJIN juga tidak sinkron (absensi=1, struk gaji=2). Ini persis anomali
yang sama dengan yang pernah ditemukan sebelumnya - tandanya fitur banding dua dokumen
ini berhasil menangkap masalah nyata, bukan cuma bug parsing.

Contoh hasil lengkap: `hasil_pemeriksaan_contoh.xlsx` (versi otomatis) dan
`hasil_pemeriksaan_sipil.xlsx` (versi SIPIL).
