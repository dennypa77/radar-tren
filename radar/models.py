"""Struktur data yang dipertukarkan antara adapter, db, dan sheets."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Sinyal:
    sumber: str  # PINTEREST | TIKTOK_CC
    periode: str  # ISO week, mis. '2026-W37'
    tanggal_ambil: date
    istilah: str
    region: str
    skor: float | None = None
    skor_satuan: str | None = None  # INDEKS_0_100 | VOLUME | RANK
    arah_perubahan: str | None = None  # NAIK | DATAR | TURUN | None
    catatan: str | None = None
    raw: str | None = None  # JSON payload asli


@dataclass
class KalenderRilis:
    tanggal_rilis: date
    kategori: str  # ANIME | KPOP | FILM | GAME | LOKAL
    judul: str
    sumber: str  # ANILIST | MANUAL
    perkiraan_minat: float | None = None
    lini_hog_relevan: str | None = None  # diisi manusia
    status_ip: str | None = None  # diisi manusia -- BERLISENSI | GENERIK | AMAN
    catatan: str | None = None
    raw: str | None = None


@dataclass
class HasilImpor:
    sinyal: list[Sinyal] = field(default_factory=list)
    peringatan: list[str] = field(default_factory=list)
