"""
rules.py
Aturan pemeriksaan anomali Laporan Rekap Absen + rumus perhitungan HKP.

Struktur data per karyawan yang diharapkan (dict), sesuai kesepakatan:
{
    "id": str,
    "nama": str,
    "group": str,               # nama group/shift, mis. "NS1", "GROUP 1 PROCESSING", dst
    "hari": [                   # satu entri per hari (biasanya 30/31 hari)
        {
            "tanggal": int,
            "jam_kerja_in": "HH:MM" atau None,
            "jam_kerja_out": "HH:MM" atau None,
            "mesin_in": "HH:MM" atau None,
            "mesin_out": "HH:MM" atau None,
            "izin": str,         # kode: '_', 'DT','CI','DR','S1','S2','PC','CN','CL','CD','?'
            "hari_kerja_faktor": float,  # nilai faktor hari kerja (0.00 - 1.00 dst)
        },
        ...
    ],
    "lembur_libur": float,
    "lembur_hkl": float,
    "tunj_masa_kerja": float,    # HKP yang dilaporkan sistem, untuk dibandingkan
}
"""

from dataclasses import dataclass, field

# Batas HKP per group untuk periode 30 hari (26/06 - 25/07)
GROUP_BATAS_HKP = {
    "NS1": 21, "NON SHIFT 1": 21,
    "NS2": 21, "NON SHIFT 2": 21,
    "NS3": 25, "NON SHIFT 3": 25,
    "GROUP 1 PROCESSING": 21,
    "GROUP 2 PROCESSING": 21,
    "GROUP 3 PROCESSING": 25,
    "UTILITY 1": 21, "UTILITY 2": 21, "UTILITY 3": 21, "UTILITY 4": 21,
    "UTILITY 5": 25, "UTILITY 6": 25,
    "SIPIL": 25,
    "SIPIL 2": 21,
}

IZIN_KOSONG = "_"
IZIN_TIDAK_STERIL = "?"
IZIN_S2_CI = {"S2", "CI"}
IZIN_DR = {"DR"}


@dataclass
class Anomali:
    nrp: str
    nama: str
    aturan: str
    detail: str
    tanggal: int = None


def cek_aturan1(karyawan):
    """Mesin Absen 00:00/00:00 -> Hari Kerja wajib 0,00"""
    hasil = []
    for h in karyawan["hari"]:
        mesin_kosong = (h.get("mesin_in") in (None, "00:00")) and (h.get("mesin_out") in (None, "00:00"))
        if mesin_kosong and h.get("hari_kerja_faktor", 0) not in (0, 0.0):
            hasil.append(Anomali(
                karyawan["id"], karyawan["nama"], "Aturan 1",
                f"Mesin absen kosong tapi Hari Kerja = {h['hari_kerja_faktor']}",
                h.get("tanggal")))
    return hasil


def cek_aturan2(karyawan):
    """Jam Kerja 00:00/00:00 (libur terjadwal) -> Izin wajib '_'"""
    hasil = []
    for h in karyawan["hari"]:
        jadwal_libur = (h.get("jam_kerja_in") in (None, "00:00")) and (h.get("jam_kerja_out") in (None, "00:00"))
        if jadwal_libur and h.get("izin", IZIN_KOSONG) != IZIN_KOSONG:
            hasil.append(Anomali(
                karyawan["id"], karyawan["nama"], "Aturan 2",
                f"Hari libur terjadwal tapi Izin = '{h['izin']}'",
                h.get("tanggal")))
    return hasil


def cek_aturan4(karyawan):
    """Kode Izin '?' -> data belum steril"""
    hasil = []
    for h in karyawan["hari"]:
        if h.get("izin") == IZIN_TIDAK_STERIL:
            hasil.append(Anomali(
                karyawan["id"], karyawan["nama"], "Aturan 4",
                "Kode izin '?' - data belum steril, tidak dihitung HKP",
                h.get("tanggal")))
    return hasil


def _is_sipil(karyawan):
    """Karyawan SIPIL memakai dokumen/rumus HKP versi tidak otomatis (dihitung
    per kehadiran, bukan batas group 21/25). Terdeteksi dari nama group yang
    mengandung kata 'SIPIL' (mis. 'SIPIL', 'SIPIL 2'), dan biasanya periode
    dokumennya juga beda (1-5 atau 16-akhir bulan, bukan 26-25)."""
    group = (karyawan.get("group") or "").upper()
    return group.startswith("SIPIL")


def hitung_hkp_sipil(karyawan):
    """Rumus HKP versi tidak otomatis (SIPIL): dihitung murni dari jumlah
    kehadiran dalam periode (jumlah faktor Hari Kerja harian, 0.00-1.00 per
    hari) - bukan dari batas group dikurangi izin. Kalau dalam periode cuma
    masuk 1x, HKP-nya cuma 1. Mengembalikan (hkp_hasil, ada_data_tidak_steril)."""
    ada_tidak_steril = any(h.get("izin") == IZIN_TIDAK_STERIL for h in karyawan["hari"])
    total = sum(h.get("hari_kerja_faktor") or 0 for h in karyawan["hari"])
    return round(total, 2), ada_tidak_steril


def hitung_hkp(karyawan, batas_override=None):
    """
    Rumus HKP (Aturan 3) - versi OTOMATIS (non-SIPIL):
    1. batas group - jumlah izin S2/CI
    2. hasil - jumlah izin DR
    3. hasil - jumlah izin lain di luar S2/CI/DR (mis. S1, dst, tidak termasuk '_' dan '?')
    Untuk karyawan SIPIL, dipakai hitung_hkp_sipil() (per kehadiran) - lihat _is_sipil().
    Mengembalikan (hkp_hasil, batas_dipakai, ada_data_tidak_steril)
    """
    if _is_sipil(karyawan):
        hkp_hasil, ada_tidak_steril = hitung_hkp_sipil(karyawan)
        return hkp_hasil, None, ada_tidak_steril

    group = karyawan.get("group", "")
    batas = batas_override if batas_override is not None else GROUP_BATAS_HKP.get(group)
    if batas is None:
        return None, None, False

    ada_tidak_steril = any(h.get("izin") == IZIN_TIDAK_STERIL for h in karyawan["hari"])

    n_s2_ci = sum(1 for h in karyawan["hari"] if h.get("izin") in IZIN_S2_CI)
    n_dr = sum(1 for h in karyawan["hari"] if h.get("izin") in IZIN_DR)
    n_lain = sum(1 for h in karyawan["hari"]
                 if h.get("izin") not in ({IZIN_KOSONG, IZIN_TIDAK_STERIL} | IZIN_S2_CI | IZIN_DR))

    hasil = batas - n_s2_ci
    hasil = hasil - n_dr
    hasil = hasil - n_lain
    return hasil, batas, ada_tidak_steril


def cek_aturan3(karyawan, batas_override=None):
    """Bandingkan HKP hasil hitung vs HKP yang dilaporkan sistem (tunj_masa_kerja)"""
    hkp_hasil, batas, ada_tidak_steril = hitung_hkp(karyawan, batas_override)
    if hkp_hasil is None:
        return [Anomali(karyawan["id"], karyawan["nama"], "Aturan 3",
                         f"Group '{karyawan.get('group')}' tidak dikenal di tabel batas HKP")]
    if ada_tidak_steril:
        return []  # sudah dilaporkan lewat Aturan 4, HKP tidak dihitung
    dilaporkan = karyawan.get("tunj_masa_kerja")
    hasil = []
    if dilaporkan is not None and round(hkp_hasil, 2) != round(dilaporkan, 2):
        hasil.append(Anomali(
            karyawan["id"], karyawan["nama"], "Aturan 3",
            f"HKP hasil hitung = {hkp_hasil}, HKP sistem = {dilaporkan} (batas group {batas})"))
    return hasil


def jalankan_semua_aturan(karyawan, batas_override=None):
    hasil = []
    hasil += cek_aturan1(karyawan)
    hasil += cek_aturan2(karyawan)
    hasil += cek_aturan3(karyawan, batas_override)
    hasil += cek_aturan4(karyawan)
    return hasil
