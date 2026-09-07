"""Sinkronisasi SQLite -> Google Sheet.

SQLite adalah kebenaran. `sync` menulis ulang isi sheet dari SQLite setiap kali,
KECUALI tiga kolom yang diisi manusia di Kalender Rilis (lini_hog_relevan,
status_ip, catatan) yang dibaca balik ke SQLite dulu sebelum ditulis ulang
(Bab 8 brief). Ini satu-satunya jalur dua arah -- jangan diperluas.
"""

from __future__ import annotations

import os
import sqlite3

import gspread

from radar.db import ambil_semua_kalender, ambil_semua_sinyal, set_kolom_manual_kalender

KOLOM_SHEET_A = [
    "sumber", "tanggal_ambil", "periode", "istilah", "skor",
    "skor_satuan", "arah_perubahan", "region", "catatan",
]
KOLOM_KALENDER = [
    "tanggal_rilis", "kategori", "judul", "perkiraan_minat",
    "lini_hog_relevan", "status_ip", "catatan",
]


class SheetsError(Exception):
    pass


def buka_spreadsheet() -> gspread.Spreadsheet:
    service_account_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service-account.json")
    sheet_id = os.environ.get("GOOGLE_SHEETS_ID", "").strip()

    if not sheet_id:
        raise SheetsError(
            "GOOGLE_SHEETS_ID belum diisi di .env. Tool ini TIDAK membuat spreadsheet baru "
            "secara otomatis (lihat Bab 11 brief -- ini pertanyaan untuk Denny). "
            "Kalau spreadsheet sudah ada, isi ID-nya (bagian antara /d/ dan /edit di URL) ke .env. "
            "Kalau belum ada, buat manual, lalu share ke email service account sebagai Editor."
        )
    if not os.path.exists(service_account_file):
        raise SheetsError(
            f"File service account tidak ditemukan: {service_account_file}. "
            "Set GOOGLE_SERVICE_ACCOUNT_FILE di .env dan pastikan file JSON-nya ada "
            "(JANGAN commit file ini ke git)."
        )

    gc = gspread.service_account(filename=service_account_file)
    try:
        return gc.open_by_key(sheet_id)
    except gspread.exceptions.APIError as e:
        raise SheetsError(f"Gagal membuka spreadsheet {sheet_id}: {e}") from e


def _ambil_atau_buat_worksheet(sh: gspread.Spreadsheet, judul: str, kolom: list[str]) -> gspread.Worksheet:
    try:
        return sh.worksheet(judul)
    except gspread.exceptions.WorksheetNotFound:
        return sh.add_worksheet(title=judul, rows=1000, cols=len(kolom) + 2)


def _baca_balik_kolom_manual(conn: sqlite3.Connection, ws: gspread.Worksheet) -> int:
    """Baca kolom lini_hog_relevan/status_ip/catatan dari sheet ke SQLite. Return jumlah baris ditulis."""
    nilai = ws.get_all_values()
    if not nilai or len(nilai) < 2:
        return 0
    header = nilai[0]
    try:
        idx = {kol: header.index(kol) for kol in KOLOM_KALENDER}
    except ValueError:
        # header sheet belum sesuai (mis. worksheet baru dibuat) -- tidak ada apa-apa untuk dibaca balik
        return 0

    ditulis = 0
    for row in nilai[1:]:
        def ambil(kol: str) -> str:
            i = idx[kol]
            return row[i] if i < len(row) else ""

        tanggal_rilis = ambil("tanggal_rilis").strip()
        kategori = ambil("kategori").strip()
        judul = ambil("judul").strip()
        if not (tanggal_rilis and kategori and judul):
            continue
        ok = set_kolom_manual_kalender(
            conn,
            kategori=kategori,
            judul=judul,
            tanggal_rilis=tanggal_rilis,
            lini_hog_relevan=ambil("lini_hog_relevan").strip() or None,
            status_ip=ambil("status_ip").strip() or None,
            catatan=ambil("catatan").strip() or None,
        )
        if ok:
            ditulis += 1
    conn.commit()
    return ditulis


def _tulis_ulang(ws: gspread.Worksheet, kolom: list[str], baris: list[list]) -> None:
    ws.clear()
    ws.update([kolom] + baris, value_input_option="USER_ENTERED")
    ws.freeze(rows=1)
    ws.format("1:1", {"textFormat": {"bold": True}})


def sync(conn: sqlite3.Connection) -> dict:
    """Return ringkasan: {baris_sheet_a, baris_kalender, kolom_manual_dibaca_balik}."""
    sh = buka_spreadsheet()

    nama_sheet_a = os.environ.get("SHEET_A_NAME", "Sheet A")
    nama_kalender = os.environ.get("SHEET_KALENDER_NAME", "Kalender Rilis")

    ws_a = _ambil_atau_buat_worksheet(sh, nama_sheet_a, KOLOM_SHEET_A)
    ws_k = _ambil_atau_buat_worksheet(sh, nama_kalender, KOLOM_KALENDER)

    # 1. Baca balik kolom manual DULU, sebelum ditulis ulang.
    kolom_manual_dibaca_balik = _baca_balik_kolom_manual(conn, ws_k)

    # 2. Tulis ulang penuh dari SQLite (sumber kebenaran).
    sinyal = ambil_semua_sinyal(conn)
    baris_a = [[row[k] for k in KOLOM_SHEET_A] for row in sinyal]
    _tulis_ulang(ws_a, KOLOM_SHEET_A, baris_a)

    kalender = ambil_semua_kalender(conn)
    baris_k = [[row[k] for k in KOLOM_KALENDER] for row in kalender]
    _tulis_ulang(ws_k, KOLOM_KALENDER, baris_k)

    return {
        "baris_sheet_a": len(baris_a),
        "baris_kalender": len(baris_k),
        "kolom_manual_dibaca_balik": kolom_manual_dibaca_balik,
    }
