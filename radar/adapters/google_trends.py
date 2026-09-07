"""Importer CSV untuk export "interest over time" dari trends.google.com.

BUKAN scraper -- operator export CSV lewat tombol export di UI Google Trends
(sama pola dengan Pinterest/TikTok, lihat Bab 5 brief). Ditambahkan atas
keputusan Denny (2026-09-07): region Indonesia tidak tersedia di Pinterest
Trends, jadi sinyal upstream Indonesia diperkuat lewat Google Trends yang
mendukung penuh region ID.

Format CSV Google Trends agak unik (bukan tabel datar biasa):

    Category: All categories

    Week,stiker custom: (Indonesia),sticker aesthetic: (Indonesia)
    2026-08-17,45,30
    2026-08-24,52,28
    ...

Satu file bisa berisi beberapa istilah sekaligus (Google Trends membolehkan
sampai 5 istilah dibandingkan dalam satu export).
"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import date
from pathlib import Path

from radar.adapters.base import KolomTidakDitemukan
from radar.models import Sinyal

_KOLOM_TANGGAL = {"day", "week", "month"}
_SUFFIX_REGION_RE = re.compile(r":\s*\([^)]*\)\s*$")


def _bersihkan_nama_istilah(nama_kolom: str) -> str:
    return _SUFFIX_REGION_RE.sub("", nama_kolom).strip()


def _cari_baris_header(baris_mentah: list[str]) -> int:
    for i, baris in enumerate(baris_mentah):
        kolom_pertama = baris.split(",", 1)[0].strip().strip('"').lower()
        if kolom_pertama in _KOLOM_TANGGAL:
            return i
    raise KolomTidakDitemukan(
        "[GOOGLE_TRENDS] Tidak ditemukan baris header (harus mulai dengan "
        "'Day'/'Week'/'Month'). Pastikan ini file export 'interest over time' "
        "dari trends.google.com, bukan file lain."
    )


def _angka(nilai: str) -> float | None:
    nilai = (nilai or "").strip()
    if nilai in ("", "<1"):
        return 0.5 if nilai == "<1" else None
    try:
        return float(nilai)
    except ValueError:
        return None


def _arah(sekarang: float | None, sebelumnya: float | None) -> str | None:
    if sekarang is None or sebelumnya is None:
        return None
    if sekarang > sebelumnya:
        return "NAIK"
    if sekarang < sebelumnya:
        return "TURUN"
    return "DATAR"


class GoogleTrendsCSVAdapter:
    nama = "GOOGLE_TRENDS"

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)

    def ambil(self, kata_pantau: list[str], region: str, periode: str) -> list[Sinyal]:
        if not self.file_path.exists():
            raise FileNotFoundError(f"File CSV tidak ditemukan: {self.file_path}")
        teks = self.file_path.read_text(encoding="utf-8-sig")
        baris_mentah = [b for b in teks.splitlines() if b.strip() != ""]

        idx_header = _cari_baris_header(baris_mentah)
        reader = csv.reader(io.StringIO("\n".join(baris_mentah[idx_header:])))
        rows = list(reader)
        header = rows[0]
        data_rows = rows[1:]

        if len(header) < 2:
            raise KolomTidakDitemukan(
                f"[GOOGLE_TRENDS] Header hanya punya {len(header)} kolom, "
                "butuh minimal 1 kolom tanggal + 1 kolom istilah."
            )
        if not data_rows:
            return []

        kolom_istilah = [(i, _bersihkan_nama_istilah(h)) for i, h in enumerate(header) if i > 0]

        hasil: list[Sinyal] = []
        hari_ini = date.today()
        baris_terakhir = data_rows[-1]
        baris_sebelumnya = data_rows[-2] if len(data_rows) >= 2 else None

        for i, istilah in kolom_istilah:
            if not istilah:
                continue
            nilai_sekarang = _angka(baris_terakhir[i]) if i < len(baris_terakhir) else None
            nilai_sebelumnya = (
                _angka(baris_sebelumnya[i]) if baris_sebelumnya and i < len(baris_sebelumnya) else None
            )
            deret = [
                {"tanggal": r[0], "nilai": r[i] if i < len(r) else None} for r in data_rows
            ]
            hasil.append(
                Sinyal(
                    sumber=self.nama,
                    periode=periode,
                    tanggal_ambil=hari_ini,
                    istilah=istilah,
                    region=region,
                    skor=nilai_sekarang,
                    skor_satuan="INDEKS_0_100",
                    arah_perubahan=_arah(nilai_sekarang, nilai_sebelumnya),
                    catatan=None,
                    raw=json.dumps(deret, ensure_ascii=False),
                )
            )
        return hasil
