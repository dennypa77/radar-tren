"""Helper untuk periode ISO week, mis. '2026-W37'."""

from __future__ import annotations

import re
from datetime import date, timedelta

_PERIODE_RE = re.compile(r"^(\d{4})-W(\d{2})$")


def periode_str(d: date) -> str:
    iso_year, iso_week, _ = d.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def periode_sekarang() -> str:
    return periode_str(date.today())


def parse_periode(periode: str) -> tuple[int, int]:
    m = _PERIODE_RE.match(periode.strip())
    if not m:
        raise ValueError(
            f"Format periode tidak valid: {periode!r}. Harus 'YYYY-Www', mis. '2026-W37'."
        )
    return int(m.group(1)), int(m.group(2))


def periode_ke_senin(periode: str) -> date:
    tahun, minggu = parse_periode(periode)
    return date.fromisocalendar(tahun, minggu, 1)


def periode_berikutnya(periode: str) -> str:
    senin = periode_ke_senin(periode)
    return periode_str(senin + timedelta(days=7))


def daftar_periode_antara(awal: str, akhir: str) -> list[str]:
    """Semua periode ISO week dari awal sampai akhir (inklusif), urut naik."""
    if parse_periode(awal) > parse_periode(akhir):
        return []
    hasil = []
    p = awal
    while parse_periode(p) <= parse_periode(akhir):
        hasil.append(p)
        p = periode_berikutnya(p)
    return hasil
