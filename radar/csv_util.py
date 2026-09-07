"""Pembaca CSV yang toleran terhadap perubahan nama kolom.

Filosofi (Bab 5.1 brief): kalau kolom yang dibutuhkan tidak ditemukan,
GAGAL dengan pesan jelas -- jangan diam-diam mengisi None.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from radar.adapters.base import KolomTidakDitemukan


def _normalisasi(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.strip().lower())


def baca_csv(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File CSV tidak ditemukan: {p}")
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        baris = [dict(row) for row in reader]
    return header, baris


def cocokkan_kolom(header: list[str], alias: dict[str, list[str]]) -> dict[str, str]:
    """Untuk tiap field logis di `alias` (field -> daftar nama kolom mungkin),
    cari nama kolom asli di header yang cocok (case/spasi/tanda baca diabaikan).

    Return: {field_logis: nama_kolom_asli}. Field yang tidak ketemu tidak masuk hasil.
    """
    header_ternormalisasi = {_normalisasi(h): h for h in header}
    hasil: dict[str, str] = {}
    for field, kandidat in alias.items():
        for k in kandidat:
            nk = _normalisasi(k)
            if nk in header_ternormalisasi:
                hasil[field] = header_ternormalisasi[nk]
                break
    return hasil


def wajibkan_kolom(
    pemetaan: dict[str, str], wajib: list[str], header: list[str], sumber: str
) -> None:
    hilang = [f for f in wajib if f not in pemetaan]
    if hilang:
        raise KolomTidakDitemukan(
            f"[{sumber}] Kolom wajib tidak ditemukan di CSV: {', '.join(hilang)}. "
            f"Kolom yang ada di file: {header}. "
            "Format export mungkin berubah -- cek nama kolom dan sesuaikan, "
            "atau laporkan supaya alias kolom di kode diperbarui."
        )
