"""Importer CSV untuk TikTok Creative Center (ads.tiktok.com/business/creativecenter).

BUKAN scraper. Tiga bagian yang didukung: keyword, hashtag, top_products.
Kalau --bagian tidak diisi, dicoba deteksi otomatis dari nama kolom.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from radar.csv_util import baca_csv, cocokkan_kolom, wajibkan_kolom
from radar.models import Sinyal

BAGIAN_VALID = ["keyword", "hashtag", "top_products"]

_ALIAS_BERSAMA = {
    "arah_perubahan": [
        "trend", "indicator", "status", "growth", "change", "arah_perubahan",
    ],
}

_ALIAS_PER_BAGIAN: dict[str, dict[str, list[str]]] = {
    "keyword": {
        "istilah": ["keyword", "term", "search term", "istilah"],
        "skor": ["search volume", "volume", "popularity", "index", "skor"],
        **_ALIAS_BERSAMA,
    },
    "hashtag": {
        "istilah": ["hashtag", "hashtag name", "tag", "istilah"],
        "skor": ["posts", "post volume", "popularity", "skor"],
        "views": ["views", "view count"],
        **_ALIAS_BERSAMA,
    },
    "top_products": {
        "istilah": ["product name", "product", "istilah"],
        "skor": ["rank", "popularity", "sales", "ctr", "skor"],
        **_ALIAS_BERSAMA,
    },
}

_SATUAN_PER_BAGIAN = {
    "keyword": "VOLUME",
    "hashtag": "VOLUME",
    "top_products": "RANK",
}

_PETA_ARAH = {
    "new": "NAIK", "rising": "NAIK", "increasing": "NAIK", "breakout": "NAIK", "hot": "NAIK", "naik": "NAIK",
    "declining": "TURUN", "decreasing": "TURUN", "falling": "TURUN", "turun": "TURUN",
    "steady": "DATAR", "stable": "DATAR", "datar": "DATAR",
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


def _deteksi_bagian(header: list[str]) -> str:
    for bagian, alias in _ALIAS_PER_BAGIAN.items():
        pemetaan = cocokkan_kolom(header, alias)
        if "istilah" in pemetaan and "skor" in pemetaan:
            return bagian
    raise ValueError(
        f"Tidak bisa mendeteksi bagian TikTok CC (keyword/hashtag/top_products) dari kolom: "
        f"{header}. Gunakan --bagian untuk menentukan manual."
    )


class TikTokCSVAdapter:
    nama = "TIKTOK_CC"

    def __init__(self, file_path: str | Path, bagian: str | None = None):
        self.file_path = Path(file_path)
        if bagian is not None and bagian not in BAGIAN_VALID:
            raise ValueError(f"--bagian harus salah satu dari {BAGIAN_VALID}, dapat {bagian!r}")
        self.bagian = bagian

    def ambil(self, kata_pantau: list[str], region: str, periode: str) -> list[Sinyal]:
        header, baris = baca_csv(self.file_path)
        bagian = self.bagian or _deteksi_bagian(header)
        alias = _ALIAS_PER_BAGIAN[bagian]
        pemetaan = cocokkan_kolom(header, alias)
        wajibkan_kolom(pemetaan, ["istilah", "skor"], header, f"{self.nama}:{bagian}")

        hasil: list[Sinyal] = []
        hari_ini = date.today()
        for row in baris:
            istilah = (row.get(pemetaan["istilah"]) or "").strip()
            if not istilah:
                continue
            kolom_arah = pemetaan.get("arah_perubahan")
            catatan_parts = [f"bagian={bagian}"]
            kolom_views = pemetaan.get("views")
            if kolom_views:
                views = _angka(row.get(kolom_views))
                if views is not None:
                    catatan_parts.append(f"views={views:g}")
            hasil.append(
                Sinyal(
                    sumber=self.nama,
                    periode=periode,
                    tanggal_ambil=hari_ini,
                    istilah=istilah,
                    region=region,
                    skor=_angka(row.get(pemetaan["skor"])),
                    skor_satuan=_SATUAN_PER_BAGIAN[bagian],
                    arah_perubahan=_arah(row.get(kolom_arah)) if kolom_arah else None,
                    catatan=", ".join(catatan_parts),
                    raw=json.dumps(row, ensure_ascii=False),
                )
            )
        return hasil
