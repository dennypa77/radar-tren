"""Importer CSV untuk Pinterest Trends (trends.pinterest.com).

BUKAN scraper -- operator menyalin data lewat UI Pinterest secara manual,
tool ini hanya membaca dan menormalisasi (lihat Bab 5.1 brief).

CATATAN PENTING (ditemukan 2026-09-07, lihat MEMORY.md/README): versi publik
Pinterest Trends TIDAK punya alat cari-per-kata-kunci seperti Google Trends --
hanya tabel "Search trends" berisi kata kunci yang SEDANG trending apa adanya
(bukan hasil pencarian salah satu dari kata_pantau kita), dengan kolom
perubahan persentase (mingguan/bulanan/tahunan), bukan indeks 0-100. Akses
lebih dalam dari 5 baris preview minta login ke akun Pinterest Business.
Denny memutuskan: pakai daftar "Search trends" apa adanya (general, bukan
filter ke 12 kata pantau) sebagai sinyal budaya visual mentah.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from radar.csv_util import baca_csv, cocokkan_kolom, wajibkan_kolom
from radar.models import Sinyal

ALIAS_KOLOM = {
    "istilah": ["keywords", "keyword", "term", "search term", "istilah", "kata kunci"],
    "mingguan": ["weekly change", "weekly", "wow", "wow change", "perubahan mingguan"],
    "bulanan": ["monthly change", "monthly", "mom", "mom change", "perubahan bulanan"],
    "tahunan": ["yearly change", "yearly", "yoy", "yoy change", "perubahan tahunan"],
}


def _angka(nilai: str | None) -> float | None:
    if nilai is None or nilai == "":
        return None
    s = str(nilai).strip().rstrip("+").rstrip("%").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _arah(persen: float | None) -> str | None:
    if persen is None:
        return None
    if persen > 0:
        return "NAIK"
    if persen < 0:
        return "TURUN"
    return "DATAR"


class PinterestCSVAdapter:
    nama = "PINTEREST"

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)

    def ambil(self, kata_pantau: list[str], region: str, periode: str) -> list[Sinyal]:
        header, baris = baca_csv(self.file_path)
        pemetaan = cocokkan_kolom(header, ALIAS_KOLOM)
        wajibkan_kolom(pemetaan, ["istilah", "mingguan"], header, self.nama)

        hasil: list[Sinyal] = []
        hari_ini = date.today()
        for row in baris:
            istilah = (row.get(pemetaan["istilah"]) or "").strip()
            if not istilah:
                continue
            mingguan = _angka(row.get(pemetaan["mingguan"]))
            bulanan = _angka(row.get(pemetaan.get("bulanan", "")))
            tahunan = _angka(row.get(pemetaan.get("tahunan", "")))
            catatan_parts = []
            if bulanan is not None:
                catatan_parts.append(f"perubahan_bulanan={bulanan:g}%")
            if tahunan is not None:
                catatan_parts.append(f"perubahan_tahunan={tahunan:g}%")
            hasil.append(
                Sinyal(
                    sumber=self.nama,
                    periode=periode,
                    tanggal_ambil=hari_ini,
                    istilah=istilah,
                    region=region,
                    skor=mingguan,
                    skor_satuan="PERSEN_PERUBAHAN_MINGGUAN",
                    arah_perubahan=_arah(mingguan),
                    catatan=", ".join(catatan_parts) if catatan_parts else None,
                    raw=json.dumps(row, ensure_ascii=False),
                )
            )
        return hasil
