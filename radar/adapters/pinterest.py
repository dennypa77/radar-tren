"""Importer CSV untuk export Pinterest Trends (trends.pinterest.com).

BUKAN scraper -- operator mengunduh/menyalin data lewat UI Pinterest secara
manual, tool ini hanya membaca dan menormalisasi (lihat Bab 5.1 brief).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from radar.csv_util import baca_csv, cocokkan_kolom, wajibkan_kolom
from radar.models import Sinyal

ALIAS_KOLOM = {
    "istilah": ["term", "keyword", "query", "trend", "search term", "istilah", "kata kunci"],
    "skor": ["index", "score", "value", "interest", "search index", "skor", "popularity"],
    "arah_perubahan": [
        "change", "trend direction", "wow change", "yoy change", "direction",
        "arah", "growth", "arah_perubahan",
    ],
}

_PETA_ARAH = {
    "up": "NAIK", "rising": "NAIK", "increasing": "NAIK", "growing": "NAIK", "naik": "NAIK",
    "down": "TURUN", "falling": "TURUN", "decreasing": "TURUN", "declining": "TURUN", "turun": "TURUN",
    "flat": "DATAR", "stable": "DATAR", "steady": "DATAR", "datar": "DATAR",
}


def _arah(nilai: str | None) -> str | None:
    if not nilai:
        return None
    return _PETA_ARAH.get(nilai.strip().lower())


def _angka(nilai: str | None) -> float | None:
    if nilai is None or nilai == "":
        return None
    try:
        return float(str(nilai).strip().rstrip("%").replace(",", ""))
    except ValueError:
        return None


class PinterestCSVAdapter:
    nama = "PINTEREST"

    def __init__(self, file_path: str | Path):
        self.file_path = Path(file_path)

    def ambil(self, kata_pantau: list[str], region: str, periode: str) -> list[Sinyal]:
        header, baris = baca_csv(self.file_path)
        pemetaan = cocokkan_kolom(header, ALIAS_KOLOM)
        wajibkan_kolom(pemetaan, ["istilah", "skor"], header, self.nama)

        hasil: list[Sinyal] = []
        hari_ini = date.today()
        for row in baris:
            istilah = (row.get(pemetaan["istilah"]) or "").strip()
            if not istilah:
                continue
            kolom_arah = pemetaan.get("arah_perubahan")
            hasil.append(
                Sinyal(
                    sumber=self.nama,
                    periode=periode,
                    tanggal_ambil=hari_ini,
                    istilah=istilah,
                    region=region,
                    skor=_angka(row.get(pemetaan["skor"])),
                    skor_satuan="INDEKS_0_100",
                    arah_perubahan=_arah(row.get(kolom_arah)) if kolom_arah else None,
                    catatan=None,
                    raw=json.dumps(row, ensure_ascii=False),
                )
            )
        return hasil
