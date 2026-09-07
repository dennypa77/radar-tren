"""SQLite = sumber kebenaran. Skema, koneksi, dan operasi baca/tulis."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from radar.models import KalenderRilis, Sinyal

SKEMA = """
CREATE TABLE IF NOT EXISTS sinyal (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  sumber         TEXT NOT NULL,          -- PINTEREST | TIKTOK_CC | GOOGLE_TRENDS
  periode        TEXT NOT NULL,
  tanggal_ambil  DATE NOT NULL,
  istilah        TEXT NOT NULL,
  skor           REAL,
  skor_satuan    TEXT,
  arah_perubahan TEXT,
  region         TEXT NOT NULL,
  catatan        TEXT,
  raw            TEXT,
  created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (sumber, periode, istilah, region)
);

CREATE TABLE IF NOT EXISTS kalender_rilis (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  tanggal_rilis     DATE NOT NULL,
  kategori          TEXT NOT NULL,
  judul             TEXT NOT NULL,
  perkiraan_minat   REAL,
  lini_hog_relevan  TEXT,
  status_ip         TEXT,
  catatan           TEXT,
  sumber            TEXT NOT NULL,
  raw               TEXT,
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (kategori, judul, tanggal_rilis)
);

CREATE TABLE IF NOT EXISTS run_log (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  sumber        TEXT NOT NULL,
  periode       TEXT NOT NULL,
  waktu_jalan   TIMESTAMP NOT NULL,
  jumlah_baris  INTEGER NOT NULL,
  status        TEXT NOT NULL,
  catatan       TEXT
);

CREATE TABLE IF NOT EXISTS meta (
  key        TEXT PRIMARY KEY,
  value      TEXT NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

STATUS_SUKSES = "SUKSES"
STATUS_GAGAL = "GAGAL"
STATUS_KOSONG = "KOSONG"
STATUS_DILEWATI = "DILEWATI"


def sambung(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_skema(conn: sqlite3.Connection) -> None:
    conn.executescript(SKEMA)
    conn.commit()


# ---- meta (dipakai untuk snapshot kata_pantau) ----

def ambil_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO meta (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
        """,
        (key, value),
    )
    conn.commit()


# ---- sinyal ----

def upsert_sinyal(conn: sqlite3.Connection, s: Sinyal) -> None:
    conn.execute(
        """
        INSERT INTO sinyal
            (sumber, periode, tanggal_ambil, istilah, skor, skor_satuan,
             arah_perubahan, region, catatan, raw)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(sumber, periode, istilah, region) DO UPDATE SET
            tanggal_ambil  = excluded.tanggal_ambil,
            skor           = excluded.skor,
            skor_satuan    = excluded.skor_satuan,
            arah_perubahan = excluded.arah_perubahan,
            catatan        = excluded.catatan,
            raw            = excluded.raw
        """,
        (
            s.sumber, s.periode, s.tanggal_ambil.isoformat(), s.istilah, s.skor,
            s.skor_satuan, s.arah_perubahan, s.region, s.catatan, s.raw,
        ),
    )


def upsert_sinyal_banyak(conn: sqlite3.Connection, daftar: list[Sinyal]) -> None:
    for s in daftar:
        upsert_sinyal(conn, s)
    conn.commit()


# ---- kalender_rilis ----

def upsert_kalender_otomatis(conn: sqlite3.Connection, k: KalenderRilis) -> None:
    """Dipakai oleh sumber otomatis (AniList). TIDAK menimpa kolom yang diisi manusia."""
    conn.execute(
        """
        INSERT INTO kalender_rilis
            (tanggal_rilis, kategori, judul, perkiraan_minat, sumber, raw)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(kategori, judul, tanggal_rilis) DO UPDATE SET
            perkiraan_minat = excluded.perkiraan_minat,
            sumber          = excluded.sumber,
            raw             = excluded.raw
        """,
        (
            k.tanggal_rilis.isoformat(), k.kategori, k.judul, k.perkiraan_minat,
            k.sumber, k.raw,
        ),
    )


def upsert_kalender_manual(conn: sqlite3.Connection, k: KalenderRilis) -> None:
    """Dipakai oleh impor CSV manual. Menulis semua kolom termasuk yang diisi manusia,
    karena baris ini MEMANG datang langsung dari input manusia."""
    conn.execute(
        """
        INSERT INTO kalender_rilis
            (tanggal_rilis, kategori, judul, perkiraan_minat, lini_hog_relevan,
             status_ip, catatan, sumber, raw)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(kategori, judul, tanggal_rilis) DO UPDATE SET
            perkiraan_minat  = excluded.perkiraan_minat,
            lini_hog_relevan = excluded.lini_hog_relevan,
            status_ip        = excluded.status_ip,
            catatan          = excluded.catatan,
            sumber           = excluded.sumber,
            raw              = excluded.raw
        """,
        (
            k.tanggal_rilis.isoformat(), k.kategori, k.judul, k.perkiraan_minat,
            k.lini_hog_relevan, k.status_ip, k.catatan, k.sumber, k.raw,
        ),
    )


def set_kolom_manual_kalender(
    conn: sqlite3.Connection,
    kategori: str,
    judul: str,
    tanggal_rilis: str,
    lini_hog_relevan: str | None,
    status_ip: str | None,
    catatan: str | None,
) -> bool:
    """Tulis balik kolom manual dari Google Sheet ke SQLite. Return True kalau baris ditemukan."""
    cur = conn.execute(
        """
        UPDATE kalender_rilis
        SET lini_hog_relevan = ?, status_ip = ?, catatan = ?
        WHERE kategori = ? AND judul = ? AND tanggal_rilis = ?
        """,
        (lini_hog_relevan, status_ip, catatan, kategori, judul, tanggal_rilis),
    )
    return cur.rowcount > 0


# ---- run_log ----

def catat_run(
    conn: sqlite3.Connection,
    sumber: str,
    periode: str,
    jumlah_baris: int,
    status: str,
    catatan: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO run_log (sumber, periode, waktu_jalan, jumlah_baris, status, catatan)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (sumber, periode, datetime.now().isoformat(timespec="seconds"), jumlah_baris, status, catatan),
    )
    conn.commit()


def ambil_semua_sinyal(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM sinyal ORDER BY periode DESC, sumber, istilah"
    ).fetchall()


def ambil_semua_kalender(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM kalender_rilis ORDER BY tanggal_rilis ASC, kategori, judul"
    ).fetchall()


def ambil_run_log(conn: sqlite3.Connection, sumber: str | None = None) -> list[sqlite3.Row]:
    if sumber:
        return conn.execute(
            "SELECT * FROM run_log WHERE sumber = ? ORDER BY periode ASC", (sumber,)
        ).fetchall()
    return conn.execute("SELECT * FROM run_log ORDER BY sumber, periode ASC").fetchall()
