"""
compare.py
Membandingkan Laporan Rekap Absen dengan Struk Gaji, dicocokkan berdasarkan NRP/ID.

Atribut yang sama di kedua dokumen dan diperiksa (memakai nilai yang SAMA-SAMA
dilaporkan oleh sistem di kedua dokumen, bukan hasil hitung ulang manual - hitung
ulang manual dari kode izin mentah adalah pemeriksaan terpisah, lihat rules.py
Aturan 3 di tab "Anomali Absensi"):
- HKP (Hari Kerja Pokok) yang dilaporkan absensi vs kolom HKP struk gaji
- IJIN (jumlah hari izin) yang dilaporkan absensi vs kolom IJIN struk gaji
- DIRUMAHKAN yang dilaporkan absensi vs kolom DIRUMAHKAN struk gaji
- LEMBURAN (jam lembur HKL) yang dilaporkan absensi vs kolom HKL struk gaji
- NAMA - dicocokkan sebagai validasi tambahan (bukan sumber angka)
"""

from dataclasses import dataclass


@dataclass
class HasilBanding:
    nrp: str
    nama_absensi: str
    nama_gaji: str
    status: str          # "COCOK", "TIDAK SINKRON", "HANYA DI ABSENSI", "HANYA DI STRUK GAJI"
    detail: list         # list of str, penjelasan tiap atribut yang beda


def bandingkan(data_absensi, data_gaji, toleransi=0.01):
    """
    data_absensi: list of dict karyawan (format absensi_parser.py / rules.py)
    data_gaji: list of dict karyawan (format gaji_parser.py)
    Mengembalikan list HasilBanding, satu per NRP (gabungan dari kedua dokumen).
    """
    by_nrp_absensi = {k["id"]: k for k in data_absensi}
    by_nrp_gaji = {k["nrp"]: k for k in data_gaji}

    semua_nrp = sorted(set(by_nrp_absensi) | set(by_nrp_gaji))
    hasil = []

    for nrp in semua_nrp:
        absen = by_nrp_absensi.get(nrp)
        gaji = by_nrp_gaji.get(nrp)

        if absen and not gaji:
            hasil.append(HasilBanding(nrp, absen["nama"], None, "HANYA DI ABSENSI",
                                       ["Karyawan ada di data absensi tapi tidak ditemukan di struk gaji"]))
            continue
        if gaji and not absen:
            hasil.append(HasilBanding(nrp, None, gaji["nama"], "HANYA DI STRUK GAJI",
                                       ["Karyawan ada di struk gaji tapi tidak ditemukan di data absensi"]))
            continue

        detail = []

        # Nama (validasi longgar, hanya info)
        if absen["nama"].strip().upper() != (gaji["nama"] or "").strip().upper():
            detail.append(f"Nama beda: absensi='{absen['nama']}' vs struk gaji='{gaji['nama']}'")

        # HKP - atribut utama (nilai yang dilaporkan absensi, field tunj_masa_kerja)
        hkp_absensi = absen.get("tunj_masa_kerja")
        hkp_gaji = gaji.get("hkp")
        if hkp_absensi is None:
            detail.append("HKP tidak terbaca dari dokumen absensi")
        elif hkp_gaji is None or abs(round(hkp_absensi, 2) - round(hkp_gaji, 2)) > toleransi:
            detail.append(f"HKP tidak sinkron: absensi = {hkp_absensi}, struk gaji = {hkp_gaji}")

        # IJIN - jumlah hari izin (nilai yang dilaporkan absensi)
        ijin_absensi = absen.get("ijin_sistem")
        ijin_gaji = gaji.get("ijin")
        if ijin_absensi is not None and ijin_gaji is not None and int(ijin_absensi) != int(ijin_gaji):
            detail.append(f"Jumlah IJIN tidak sinkron: absensi = {int(ijin_absensi)}, struk gaji = {ijin_gaji}")

        # DIRUMAHKAN
        dirumahkan_absensi = absen.get("dirumahkan_sistem")
        dirumahkan_gaji = gaji.get("dirumahkan")
        if dirumahkan_absensi is not None and dirumahkan_gaji is not None \
                and int(dirumahkan_absensi) != int(dirumahkan_gaji):
            detail.append(f"Jumlah DIRUMAHKAN tidak sinkron: absensi = {int(dirumahkan_absensi)}, "
                           f"struk gaji = {dirumahkan_gaji}")

        # LEMBURAN (jam, kolom HKL)
        lembur_absensi = absen.get("lembur_hkl")
        lembur_gaji = gaji.get("hkl")
        if lembur_absensi is not None and lembur_gaji is not None \
                and abs(round(lembur_absensi, 2) - round(lembur_gaji, 2)) > toleransi:
            detail.append(f"Jam LEMBURAN tidak sinkron: absensi = {lembur_absensi}, struk gaji = {lembur_gaji}")

        status = "COCOK" if not detail else "TIDAK SINKRON"
        hasil.append(HasilBanding(nrp, absen["nama"], gaji["nama"], status, detail))

    return hasil


def ringkasan(hasil_banding):
    total = len(hasil_banding)
    cocok = sum(1 for h in hasil_banding if h.status == "COCOK")
    tidak_sinkron = sum(1 for h in hasil_banding if h.status == "TIDAK SINKRON")
    hanya_absensi = sum(1 for h in hasil_banding if h.status == "HANYA DI ABSENSI")
    hanya_gaji = sum(1 for h in hasil_banding if h.status == "HANYA DI STRUK GAJI")
    return {
        "total": total, "cocok": cocok, "tidak_sinkron": tidak_sinkron,
        "hanya_di_absensi": hanya_absensi, "hanya_di_struk_gaji": hanya_gaji,
    }
