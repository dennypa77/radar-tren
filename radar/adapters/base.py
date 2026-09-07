"""Antarmuka bersama semua sumber sinyal.

Kalau antarmuka ini dijaga konsisten, mengganti importer CSV manual menjadi
otomatis (scraper/API resmi) di masa depan tidak akan menyentuh kode hilir
(db, sheets, cli) sama sekali -- lihat Bab 5 brief.
"""

from __future__ import annotations

from typing import Protocol

from radar.models import Sinyal


class SumberAdapter(Protocol):
    nama: str

    def ambil(self, kata_pantau: list[str], region: str, periode: str) -> list[Sinyal]:
        ...


class KolomTidakDitemukan(Exception):
    """CSV tidak punya kolom yang dibutuhkan -- gagal jelas, jangan diam-diam isi None."""
