"""Importer CSV manual untuk kategori kalender rilis non-anime
(K-pop, film, game, lokal -- lihat Bab 5.3 brief). Skema sama dengan tabel kalender_rilis.
"""

from __future__ import annotations

import json
from datetime import date, datetime

from radar.adapters.base import KolomTidakDitemukan
from radar.csv_util import baca_csv, cocokkan_kolom, wajibkan_kolom
from radar.models import KalenderRilis

ALIAS_KOLOM = {
    "tanggal_rilis": ["tanggal_rilis", "release date", "tanggal", "date"],
    "kategori": ["kategori", "category"],
    "judul": ["judul", "title", "nama"],
    "perkiraan_minat": ["perkiraan_minat", "interest", "popularity", "skor"],
    "lini_hog_relevan": ["lini_hog_relevan", "lini_hog", "product line"],
    "status_ip": ["status_ip", "ip status"],
    "catatan": ["catatan", "notes", "note"],
}

KATEGORI_VALID = ["ANIME", "KPOP", "FILM", "GAME", "LOKAL"]


def _tanggal(nilai: str) -> date:
    nilai = nilai.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(nilai, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Format tanggal tidak dikenali: {nilai!r} (gunakan YYYY-MM-DD)")


def _angka(nilai: str | None) -> float | None:
    if nilai is None or nilai == "":
        return None
    try:
        return float(str(nilai).strip().replace(",", ""))
    except ValueError:
        return None


def baca_kalender_manual(file_path: str) -> list[KalenderRilis]:
    header, baris = baca_csv(file_path)
    pemetaan = cocokkan_kolom(header, ALIAS_KOLOM)
    wajibkan_kolom(pemetaan, ["tanggal_rilis", "kategori", "judul"], header, "KALENDER_MANUAL")

    hasil: list[KalenderRilis] = []
    for i, row in enumerate(baris, start=2):  # baris 1 = header
        judul = (row.get(pemetaan["judul"]) or "").strip()
        if not judul:
            continue
        kategori = (row.get(pemetaan["kategori"]) or "").strip().upper()
        if kategori not in KATEGORI_VALID:
            raise KolomTidakDitemukan(
                f"[KALENDER_MANUAL] Baris {i}: kategori {kategori!r} tidak dikenal. "
                f"Harus salah satu dari {KATEGORI_VALID}."
            )
        try:
            tgl = _tanggal(row[pemetaan["tanggal_rilis"]])
        except ValueError as e:
            raise KolomTidakDitemukan(f"[KALENDER_MANUAL] Baris {i}: {e}") from e

        hasil.append(
            KalenderRilis(
                tanggal_rilis=tgl,
                kategori=kategori,
                judul=judul,
                perkiraan_minat=_angka(row.get(pemetaan.get("perkiraan_minat", ""))),
                lini_hog_relevan=(row.get(pemetaan.get("lini_hog_relevan", "")) or "").strip() or None,
                status_ip=(row.get(pemetaan.get("status_ip", "")) or "").strip() or None,
                catatan=(row.get(pemetaan.get("catatan", "")) or "").strip() or None,
                sumber="MANUAL",
                raw=json.dumps(row, ensure_ascii=False),
            )
        )
    return hasil
