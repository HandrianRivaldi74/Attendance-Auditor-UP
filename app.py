"""
app.py
Aplikasi desktop pemeriksa Laporan Rekap Absen, dengan fitur baru:
membandingkan hasil absensi dengan Struk Gaji (Laporan Upah Karyawan).

Alur:
1. Buka PDF Laporan Rekap Absen -> jalankan Aturan 1-4 (rules.py) -> tabel anomali
2. (Baru) Buka PDF Struk Gaji -> parse (gaji_parser.py)
3. (Baru) Jalankan "Bandingkan" -> cocokkan per NRP (compare.py) -> tabel status
   COCOK / TIDAK SINKRON / HANYA DI ABSENSI / HANYA DI STRUK GAJI
4. Ekspor semua hasil ke Excel (exporter.py)
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import rules
import absensi_parser
import gaji_parser
import compare
import exporter


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pemeriksa Absensi & Struk Gaji - PT. URASE PRIMA")
        self.geometry("1100x700")

        self.data_absensi = []      # list dict (format rules.py)
        self.anomali_absensi = []   # list Anomali
        self.data_gaji = []         # list dict (format gaji_parser.py)
        self.hasil_banding = []     # list HasilBanding

        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")

        ttk.Button(top, text="1. Buka PDF Absensi", command=self.buka_absensi).pack(side="left", padx=4)
        self.lbl_absensi = ttk.Label(top, text="belum ada file")
        self.lbl_absensi.pack(side="left", padx=4)

        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=10)

        ttk.Button(top, text="2. Buka PDF Struk Gaji", command=self.buka_gaji).pack(side="left", padx=4)
        self.lbl_gaji = ttk.Label(top, text="belum ada file")
        self.lbl_gaji.pack(side="left", padx=4)

        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=10)

        ttk.Button(top, text="3. Bandingkan", command=self.jalankan_banding).pack(side="left", padx=4)
        ttk.Button(top, text="Ekspor ke Excel", command=self.ekspor).pack(side="left", padx=4)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        # Tab 1: Anomali absensi
        frame1 = ttk.Frame(self.notebook)
        self.notebook.add(frame1, text="Anomali Absensi")
        self.tree_anomali = self._buat_tabel(frame1, ["NRP", "Nama", "Aturan", "Detail", "Tanggal"])

        # Tab 2: Banding
        frame2 = ttk.Frame(self.notebook)
        self.notebook.add(frame2, text="Banding Absensi vs Struk Gaji")
        self.tree_banding = self._buat_tabel(
            frame2, ["NRP", "Nama (Absensi)", "Nama (Struk Gaji)", "Status", "Detail Perbedaan"])

        self.status_bar = ttk.Label(self, text="Siap.", relief="sunken", anchor="w")
        self.status_bar.pack(fill="x", side="bottom")

    def _buat_tabel(self, parent, kolom):
        tree = ttk.Treeview(parent, columns=kolom, show="headings")
        for k in kolom:
            tree.heading(k, text=k)
            tree.column(k, width=150, anchor="w")
        vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        tree.tag_configure("bad", background="#fce4e4")
        tree.tag_configure("ok", background="#e2f0d9")
        return tree

    # ---------- Aksi ----------
    def buka_absensi(self):
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            self.data_absensi = absensi_parser.parse_absensi(path)
        except Exception as e:
            messagebox.showerror("Gagal membaca PDF Absensi", str(e))
            return
        self.lbl_absensi.config(text=os.path.basename(path) + f" ({len(self.data_absensi)} karyawan)")
        self._jalankan_aturan_absensi()

    def buka_gaji(self):
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if not path:
            return
        try:
            self.data_gaji = gaji_parser.parse_struk_gaji(path)
        except Exception as e:
            messagebox.showerror("Gagal membaca PDF Struk Gaji", str(e))
            return
        self.lbl_gaji.config(text=os.path.basename(path) + f" ({len(self.data_gaji)} karyawan)")
        self.status_bar.config(text=f"Struk gaji dimuat: {len(self.data_gaji)} karyawan.")

    def _jalankan_aturan_absensi(self):
        self.anomali_absensi = []
        for k in self.data_absensi:
            self.anomali_absensi += rules.jalankan_semua_aturan(k)
        self.tree_anomali.delete(*self.tree_anomali.get_children())
        for a in self.anomali_absensi:
            self.tree_anomali.insert("", "end", values=(a.nrp, a.nama, a.aturan, a.detail, a.tanggal), tags=("bad",))
        self.status_bar.config(text=f"Absensi diperiksa: {len(self.data_absensi)} karyawan, "
                                     f"{len(self.anomali_absensi)} anomali ditemukan.")

    def jalankan_banding(self):
        if not self.data_absensi:
            messagebox.showwarning("Data belum lengkap", "Buka dulu PDF Absensi (langkah 1).")
            return
        if not self.data_gaji:
            messagebox.showwarning("Data belum lengkap", "Buka dulu PDF Struk Gaji (langkah 2).")
            return
        self.hasil_banding = compare.bandingkan(self.data_absensi, self.data_gaji)
        self.tree_banding.delete(*self.tree_banding.get_children())
        for h in self.hasil_banding:
            tag = "ok" if h.status == "COCOK" else "bad"
            self.tree_banding.insert("", "end", values=(
                h.nrp, h.nama_absensi, h.nama_gaji, h.status, "; ".join(h.detail)), tags=(tag,))
        ring = compare.ringkasan(self.hasil_banding)
        self.status_bar.config(
            text=f"Banding selesai: {ring['cocok']} cocok, {ring['tidak_sinkron']} tidak sinkron, "
                 f"{ring['hanya_di_absensi']} hanya di absensi, {ring['hanya_di_struk_gaji']} hanya di struk gaji.")
        self.notebook.select(1)

    def ekspor(self):
        if not self.anomali_absensi and not self.hasil_banding:
            messagebox.showwarning("Belum ada hasil", "Jalankan pemeriksaan/banding dulu sebelum ekspor.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
                                             initialfile="hasil_pemeriksaan.xlsx")
        if not path:
            return
        ring = compare.ringkasan(self.hasil_banding) if self.hasil_banding else None
        exporter.ekspor_hasil(path, self.anomali_absensi, self.hasil_banding, ring)
        messagebox.showinfo("Selesai", f"Hasil diekspor ke:\n{path}")


if __name__ == "__main__":
    App().mainloop()
