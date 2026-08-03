"""
absensi_parser.py (v2 - dikalibrasi dengan file PDF asli
report_laporan_rekap_absensi_hkp_otomatis__2_.pdf)

Template PDF-nya berupa 2 kolom absolut per baris karyawan:
- kolom kiri (x0 sekitar 20-30): No urut, lalu Group (1-2 baris), lalu Bagian
- kolom kanan (x0 sekitar 90-180): NRP, lalu Nama (1-3 baris), lalu Posisi/Jabatan
  keduanya sejajar top: No==NRP (top T), Group/Nama mulai top T+15..T+49,
  Bagian/Posisi selalu di top T+50..T+60 (offset tetap, berapapun jumlah baris nama/group)
- kolom kanan jauh (x0 sekitar 936-1040): label ringkasan HKP/HKL/LL/IZIN/DIRUMAHKAN
  dengan nilai (hitungan) di sebelahnya (x0 sekitar 1015-1042), berada di top T-30..T+35
- grid 31 hari (tanggal, Jam Kerja, Mesin Absen, Lembur+Izin, Hari Kerja) diambil
  lewat page.extract_tables() yang sudah terverifikasi rapi (4 baris x 31 kolom
  per karyawan, satu tabel per karyawan, urut sesuai urutan halaman)
"""

import re
import pdfplumber

LABELS_RINGKASAN = ["HKP", "HKL", "LL", "IZIN", "DIRUMAHKAN"]


def _to_float(s):
    if s is None:
        return None
    s = str(s).strip().strip(",")
    if s in ("", "-"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").strip()
    s = s.replace(".", "").replace(",", ".")
    if s in ("", "-"):
        return None
    try:
        v = float(s)
        return -v if neg else v
    except ValueError:
        return None


def _cluster_text(words, x_min, x_max, top_min, top_max):
    """Ambil semua kata dalam kotak (x_min,x_max)x(top_min,top_max), urutkan
    top lalu x, gabung jadi satu string (spasi antar kata, baris baru bila top beda)."""
    sel = [w for w in words if x_min <= w["x0"] <= x_max and top_min <= w["top"] <= top_max]
    sel.sort(key=lambda w: (round(w["top"], 1), w["x0"]))
    lines = {}
    for w in sel:
        key = round(w["top"], 0)
        lines.setdefault(key, []).append(w["text"])
    out = []
    for k in sorted(lines):
        out.append(" ".join(lines[k]))
    return " ".join(out).strip()


def _parse_page(page):
    words = page.extract_words()
    tables = page.extract_tables()

    # 1) cari anchor NRP: x0 di kolom kanan-dekat (90-108), teks murni digit 4-7 char
    anchors = []
    for w in words:
        if 88 <= w["x0"] <= 108 and re.fullmatch(r"\d{3,7}", w["text"]):
            anchors.append((w["top"], w["text"]))
    anchors.sort(key=lambda a: a[0])

    hasil = []
    for idx, (T, nrp) in enumerate(anchors):
        nama = _cluster_text(words, 88, 180, T + 12, T + 49)
        group = _cluster_text(words, 18, 88, T + 12, T + 49)
        bagian = _cluster_text(words, 18, 88, T + 50, T + 62)
        posisi = _cluster_text(words, 88, 180, T + 50, T + 62)

        # 2) ringkasan HKP/HKL/LL/IZIN/DIRUMAHKAN: label x0~936.6, nilai (hitungan) x0~1015-1042
        ringkasan = {}
        for w in words:
            if 930 <= w["x0"] <= 996 and w["text"] in LABELS_RINGKASAN and (T - 32) <= w["top"] <= (T + 36):
                label = w["text"]
                nilai_words = [v for v in words
                                if 1015 <= v["x0"] <= 1042 and abs(v["top"] - w["top"]) < 1.5]
                if nilai_words:
                    ringkasan[label] = _to_float(nilai_words[0]["text"])

        # 3) grid 31 hari dari tabel ke-idx pada halaman ini (asumsi urutan sama)
        tabel = tables[idx] if idx < len(tables) else None

        hasil.append({
            "id": nrp,
            "nama": nama,
            "group": group,
            "bagian": bagian,
            "posisi": posisi,
            "hkp_sistem": ringkasan.get("HKP"),
            "hkl": ringkasan.get("HKL"),
            "ll": ringkasan.get("LL"),
            "ijin_sistem": ringkasan.get("IZIN"),
            "dirumahkan_sistem": ringkasan.get("DIRUMAHKAN"),
            "tabel_grid": tabel,
        })
    return hasil


def _to_float_faktor(s):
    """Kolom 'Hari Kerja' (faktor harian 0.00-1.00) memakai TITIK sebagai
    desimal (mis. '1.00', ',97', ',88'), beda dari kolom lain yang memakai
    koma sebagai desimal dan titik sebagai pemisah ribuan. Parser umum
    _to_float akan salah baca '1.00' jadi 100.0, jadi dipakai fungsi khusus."""
    if s is None:
        return None
    s = str(s).strip()
    if s in ("", "-"):
        return None
    if s.startswith(","):
        s = "0" + s.replace(",", ".", 1)
    try:
        return float(s)
    except ValueError:
        return _to_float(s)


def _grid_ke_hari(tabel):
    """tabel: list 4 baris x 31 kolom -> [Jam Kerja, Mesin Absen, Lembur+Izin, Hari Kerja]
    kolom kosong ('') = tanggal tidak ada di bulan itu (mis. tanggal 31 di bulan 30 hari) -> dilewati.
    """
    hari = []
    if not tabel or len(tabel) < 4:
        return hari
    baris_jam, baris_mesin, baris_lembur_izin, baris_hk = tabel[0], tabel[1], tabel[2], tabel[3]
    n = len(baris_jam)
    for i in range(n):
        jam = (baris_jam[i] or "").strip()
        if jam == "" and (baris_mesin[i] or "").strip() == "":
            continue  # tanggal tidak ada di bulan ini
        jam_parts = jam.split("\n")
        jk_in = jam_parts[0] if len(jam_parts) > 0 else None
        jk_out = jam_parts[1] if len(jam_parts) > 1 else None

        mesin = (baris_mesin[i] or "").strip().split("\n")
        m_in = mesin[0] if len(mesin) > 0 else None
        m_out = mesin[1] if len(mesin) > 1 else None

        li = (baris_lembur_izin[i] or "").strip().split("\n")
        lembur_hkl = _to_float(li[0]) if len(li) > 0 else None
        izin = li[1] if len(li) > 1 else "_"

        hk = _to_float_faktor((baris_hk[i] or "").strip())

        hari.append({
            "tanggal": i + 1,
            "jam_kerja_in": jk_in, "jam_kerja_out": jk_out,
            "mesin_in": m_in, "mesin_out": m_out,
            "izin": izin if izin else "_",
            "hari_kerja_faktor": hk if hk is not None else 0.0,
            "lembur_hkl_hari": lembur_hkl,
        })
    return hari


def parse_absensi(pdf_path):
    """Mengembalikan list of dict sesuai format rules.py, ditambah field
    tambahan (bagian, posisi, hkp_sistem, ijin_sistem, dirumahkan_sistem)
    yang dipakai compare.py."""
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for k in _parse_page(page):
                hari = _grid_ke_hari(k.pop("tabel_grid"))
                lembur_hkl_total = sum(h["lembur_hkl_hari"] or 0 for h in hari) or k.get("hkl")
                out.append({
                    "id": k["id"],
                    "nama": k["nama"],
                    "group": k["group"],
                    "bagian": k["bagian"],
                    "posisi": k["posisi"],
                    "hari": hari,
                    "lembur_libur": k.get("ll") or 0,
                    "lembur_hkl": lembur_hkl_total or 0,
                    "tunj_masa_kerja": k.get("hkp_sistem"),
                    "ijin_sistem": k.get("ijin_sistem"),
                    "dirumahkan_sistem": k.get("dirumahkan_sistem"),
                })
    return out


if __name__ == "__main__":
    import sys, json
    data = parse_absensi(sys.argv[1])
    print(f"Total karyawan terbaca: {len(data)}")
    for d in data[:3]:
        print(d["id"], d["nama"], "|", d["group"], "|", d["bagian"], "|", d["posisi"],
              "| HKP sistem:", d["tunj_masa_kerja"], "| IJIN sistem:", d["ijin_sistem"],
              "| DIRUMAHKAN sistem:", d["dirumahkan_sistem"], "| hari terbaca:", len(d["hari"]))
