"""
gaji_parser.py
Parser untuk "LAPORAN UPAH KARYAWAN" (struk gaji) PDF.

Struktur tabel per baris karyawan (hasil extract_table pdfplumber):
[NO, "NRP\\nNAMA", HKL, LL, HKP, IJIN, DIRUMAHKAN, U.POKOK, U.LEMBUR,
 U.LEMBUR_LIBUR, UPAH_IJIN, UPAH_DIRUMAHKAN, "U.LAIN-LAIN\\nTRANSPORT",
 "TUNJANGAN\\nT.JABATAN\\nT.KHUSUS", UPAH_KOTOR, "BPJS_KT\\nBPJS_KS\\nPOT.LAIN",
 U.BERSIH, KETERANGAN, TTD]

Baris "TOTAL ..." adalah subtotal per bagian/departemen, bukan data karyawan - dilewati.
"""

import re
import pdfplumber


def _to_float(s):
    if s is None:
        return None
    s = s.strip()
    if s == "" or s == "-":
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    s = s.replace(".", "").replace(",", ".")
    try:
        val = float(s)
        return -val if neg else val
    except ValueError:
        return None


def _to_int(s):
    v = _to_float(s)
    return int(v) if v is not None else None


def _split_multiline(cell, n):
    """Pecah cell multi-baris ('a\\nb\\nc') jadi list float, isi None kalau kurang."""
    if cell is None:
        parts = []
    else:
        parts = [p for p in cell.split("\n") if p.strip() != ""]
    vals = [_to_float(p) for p in parts]
    while len(vals) < n:
        vals.append(None)
    return vals[:n]


def parse_struk_gaji(pdf_path):
    """
    Mengembalikan list of dict, satu per karyawan:
    {
        nrp, nama, departemen, bagian,
        hkl, ll, hkp, ijin, dirumahkan,
        u_pokok, u_lembur, u_lembur_libur, upah_ijin, upah_dirumahkan,
        u_lain_lain, transport, tunjangan, t_jabatan, t_khusus,
        upah_kotor, bpjs_kt, bpjs_ks, pot_lain, u_bersih
    }
    """
    karyawan_list = []
    departemen, bagian = None, None
    # antrian label DEPARTEMENT/BAGIAN global (FIFO) - perlu ini karena kadang
    # header dicetak di akhir halaman N tapi tabelnya baru muncul di halaman N+1
    pending_labels = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            deps = [d.strip() for d in re.findall(r"DEPARTEMENT\s+([A-Z0-9 .,/-]+)", text)]
            bags = [b.strip() for b in re.findall(r"BAGIAN\s+([A-Z0-9 .,/-]+)", text)]
            for i in range(max(len(deps), len(bags))):
                pending_labels.append((
                    deps[i] if i < len(deps) else None,
                    bags[i] if i < len(bags) else None,
                ))

            tables = page.extract_tables()
            for table in tables:
                if pending_labels:
                    d, b = pending_labels.pop(0)
                    departemen = d or departemen
                    bagian = b or bagian
                for row in table:
                    if not row or len(row) < 17:
                        continue
                    no_cell = (row[0] or "").strip()
                    if not no_cell.isdigit():
                        continue  # lewati header/TOTAL/baris lain

                    nrp_nama = (row[1] or "").split("\n")
                    nrp = nrp_nama[0].strip() if nrp_nama else None
                    nama = " ".join(p.strip() for p in nrp_nama[1:]).strip()

                    u_lain, transport = _split_multiline(row[12], 2)
                    tunjangan, t_jabatan, t_khusus = _split_multiline(row[13], 3)
                    bpjs_kt, bpjs_ks, pot_lain = _split_multiline(row[15], 3)

                    karyawan_list.append({
                        "nrp": nrp,
                        "nama": nama,
                        "departemen": departemen,
                        "bagian": bagian,
                        "hkl": _to_float(row[2]),
                        "ll": _to_float(row[3]),
                        "hkp": _to_float(row[4]),
                        "ijin": _to_int(row[5]),
                        "dirumahkan": _to_int(row[6]),
                        "u_pokok": _to_float(row[7]),
                        "u_lembur": _to_float(row[8]),
                        "u_lembur_libur": _to_float(row[9]),
                        "upah_ijin": _to_float(row[10]),
                        "upah_dirumahkan": _to_float(row[11]),
                        "u_lain_lain": u_lain,
                        "transport": transport,
                        "tunjangan": tunjangan,
                        "t_jabatan": t_jabatan,
                        "t_khusus": t_khusus,
                        "upah_kotor": _to_float(row[14]),
                        "bpjs_kt": bpjs_kt,
                        "bpjs_ks": bpjs_ks,
                        "pot_lain": pot_lain,
                        "u_bersih": _to_float(row[16]),
                    })
    return karyawan_list


if __name__ == "__main__":
    import sys, json
    data = parse_struk_gaji(sys.argv[1])
    print(f"Total karyawan terbaca: {len(data)}")
    print(json.dumps(data[:3], indent=2, ensure_ascii=False))
