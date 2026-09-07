"""CLI 'radar' -- lihat README.md untuk alur mingguan lengkap."""

from __future__ import annotations

import os
import re
import sys
import sqlite3
from datetime import date
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from radar import db
from radar.adapters.anilist import AniListAdapter, AniListError, MUSIM_VALID
from radar.adapters.base import KolomTidakDitemukan
from radar.adapters.google_trends import GoogleTrendsCSVAdapter
from radar.adapters.pinterest import PinterestCSVAdapter
from radar.adapters.tiktok import BAGIAN_VALID, TikTokCSVAdapter
from radar.config import ConfigError, KataPantauTerkunciError, muat_config, tegakkan_kunci
from radar.kalender_manual import baca_kalender_manual
from radar.periode import daftar_periode_antara, periode_sekarang

load_dotenv()

# Codepage default terminal Windows (mis. GBK/CP1252) sering tidak bisa
# menampilkan karakter non-ASCII -- paksa UTF-8 supaya output CLI tidak crash.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(add_completion=False, help="Radar Tren Desain -- pengumpul sinyal tren mingguan HOG.")
console = Console()

SUMBER_MINGGUAN = ["PINTEREST", "TIKTOK_CC", "GOOGLE_TRENDS"]


def _db_path() -> Path:
    return Path(os.environ.get("RADAR_DB_PATH", "radar.db"))


def _config_path() -> Path:
    return Path(os.environ.get("RADAR_CONFIG_PATH", "config/kata_pantau.yaml"))


def _sambung() -> sqlite3.Connection:
    p = _db_path()
    if not p.exists():
        console.print(f"[red]Database belum ada di {p}. Jalankan 'radar init' dulu.[/red]")
        raise typer.Exit(1)
    return db.sambung(p)


def _muat_config_dan_tegakkan(conn: sqlite3.Connection, terima_perubahan: bool = False):
    try:
        cfg = muat_config(_config_path())
    except ConfigError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    if terima_perubahan:
        db.set_meta(conn, "kata_pantau_snapshot", _snapshot_langsung(cfg))
        return cfg

    try:
        tegakkan_kunci(
            cfg,
            ambil_meta=lambda k: db.ambil_meta(conn, k),
            set_meta=lambda k, v: db.set_meta(conn, k, v),
        )
    except KataPantauTerkunciError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e
    return cfg


def _snapshot_langsung(cfg) -> str:
    import json
    return json.dumps(sorted(cfg.kata_pantau), ensure_ascii=False)


@app.command()
def init(
    terima_perubahan_kata_pantau: bool = typer.Option(
        False,
        "--terima-perubahan-kata-pantau",
        help="Simpan daftar kata_pantau saat ini sebagai baseline baru, walau sebelum dikunci_sampai.",
    )
):
    """Buat DB + skema, dan validasi config."""
    p = _db_path()
    baru = not p.exists()
    conn = db.sambung(p)
    db.init_skema(conn)

    try:
        cfg = muat_config(_config_path())
    except ConfigError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    _muat_config_dan_tegakkan(conn, terima_perubahan=terima_perubahan_kata_pantau)

    console.print(f"[green]DB {'dibuat' if baru else 'sudah ada'}[/green] di {p}")
    console.print(f"Config OK: {len(cfg.kata_pantau)} kata pantau, region_utama={cfg.region_utama}, "
                  f"dikunci_sampai={cfg.dikunci_sampai}")
    conn.close()


@app.command()
def impor(
    sumber: str = typer.Option(..., "--sumber", help="pinterest | tiktok | google-trends"),
    file: Path = typer.Option(..., "--file", exists=True, help="Path file CSV hasil export."),
    periode: Optional[str] = typer.Option(None, "--periode", help="ISO week, mis. 2026-W37. Default: minggu ini."),
    region: Optional[str] = typer.Option(None, "--region", help="Default: region_utama dari config."),
    bagian: Optional[str] = typer.Option(
        None, "--bagian", help=f"Khusus TikTok: {BAGIAN_VALID}. Default: deteksi otomatis."
    ),
):
    """Impor export CSV Pinterest Trends, TikTok Creative Center, atau Google Trends."""
    conn = _sambung()
    cfg = _muat_config_dan_tegakkan(conn)

    periode = periode or periode_sekarang()
    region = region or cfg.region_utama
    sumber_norm = re.sub(r"[^a-z]", "", sumber.strip().lower())

    if sumber_norm == "pinterest":
        adapter = PinterestCSVAdapter(file)
        nama_sumber = adapter.nama
    elif sumber_norm == "tiktok":
        if bagian and bagian not in BAGIAN_VALID:
            console.print(f"[red]--bagian harus salah satu dari {BAGIAN_VALID}[/red]")
            raise typer.Exit(1)
        adapter = TikTokCSVAdapter(file, bagian=bagian)
        nama_sumber = adapter.nama
    elif sumber_norm == "googletrends":
        adapter = GoogleTrendsCSVAdapter(file)
        nama_sumber = adapter.nama
    else:
        console.print("[red]--sumber harus 'pinterest', 'tiktok', atau 'google-trends'[/red]")
        raise typer.Exit(1)

    try:
        sinyal = adapter.ambil(cfg.kata_pantau, region, periode)
    except (KolomTidakDitemukan, ValueError, FileNotFoundError) as e:
        console.print(f"[red]Impor gagal: {e}[/red]")
        db.catat_run(conn, nama_sumber, periode, 0, db.STATUS_GAGAL, catatan=str(e))
        raise typer.Exit(1) from e

    if not sinyal:
        console.print(f"[yellow]File {file} terbaca tapi tidak ada baris valid (KOSONG).[/yellow]")
        db.catat_run(conn, nama_sumber, periode, 0, db.STATUS_KOSONG, catatan=f"file={file}")
        raise typer.Exit(0)

    db.upsert_sinyal_banyak(conn, sinyal)
    db.catat_run(conn, nama_sumber, periode, len(sinyal), db.STATUS_SUKSES, catatan=f"file={file}")
    console.print(f"[green]OK[/green] {len(sinyal)} baris {nama_sumber} periode {periode} diimpor/diperbarui.")
    conn.close()


@app.command("kalender-ambil")
def kalender_ambil(
    musim: str = typer.Option(..., "--musim", help=f"Salah satu dari {MUSIM_VALID}"),
    tahun: int = typer.Option(..., "--tahun"),
):
    """Ambil kalender rilis anime dari AniList (otomatis)."""
    conn = _sambung()
    periode_run = f"{tahun}-{musim.upper()}"

    try:
        adapter = AniListAdapter()
        kalender = adapter.ambil_musim(musim, tahun)
    except (AniListError, ValueError) as e:
        console.print(f"[red]Gagal ambil dari AniList: {e}[/red]")
        db.catat_run(conn, "ANILIST", periode_run, 0, db.STATUS_GAGAL, catatan=str(e))
        raise typer.Exit(1) from e

    if not kalender:
        console.print(f"[yellow]Tidak ada anime ditemukan untuk {musim} {tahun} (KOSONG).[/yellow]")
        db.catat_run(conn, "ANILIST", periode_run, 0, db.STATUS_KOSONG)
        raise typer.Exit(0)

    for k in kalender:
        db.upsert_kalender_otomatis(conn, k)
    conn.commit()
    db.catat_run(conn, "ANILIST", periode_run, len(kalender), db.STATUS_SUKSES)
    console.print(f"[green]OK[/green] {len(kalender)} judul anime {musim} {tahun} diimpor/diperbarui.")
    conn.close()


@app.command("kalender-impor")
def kalender_impor(
    file: Path = typer.Option(..., "--file", exists=True, help="CSV kategori non-anime (KPOP/FILM/GAME/LOKAL)."),
):
    """Impor kalender rilis manual (kategori selain anime)."""
    conn = _sambung()
    periode_run = periode_sekarang()

    try:
        kalender = baca_kalender_manual(str(file))
    except (KolomTidakDitemukan, ValueError) as e:
        console.print(f"[red]Impor gagal: {e}[/red]")
        db.catat_run(conn, "MANUAL", periode_run, 0, db.STATUS_GAGAL, catatan=str(e))
        raise typer.Exit(1) from e

    if not kalender:
        console.print(f"[yellow]File {file} terbaca tapi tidak ada baris valid (KOSONG).[/yellow]")
        db.catat_run(conn, "MANUAL", periode_run, 0, db.STATUS_KOSONG, catatan=f"file={file}")
        raise typer.Exit(0)

    for k in kalender:
        db.upsert_kalender_manual(conn, k)
    conn.commit()
    db.catat_run(conn, "MANUAL", periode_run, len(kalender), db.STATUS_SUKSES, catatan=f"file={file}")
    console.print(f"[green]OK[/green] {len(kalender)} baris kalender manual diimpor/diperbarui.")
    conn.close()


@app.command()
def sync():
    """Tulis ulang SQLite -> Google Sheet (Sheet A + Kalender Rilis)."""
    from radar.sheets import SheetsError
    from radar.sheets import sync as sheets_sync

    conn = _sambung()
    periode_run = periode_sekarang()
    try:
        ringkasan = sheets_sync(conn)
    except SheetsError as e:
        console.print(f"[red]Sync gagal: {e}[/red]")
        db.catat_run(conn, "SYNC", periode_run, 0, db.STATUS_GAGAL, catatan=str(e))
        raise typer.Exit(1) from e

    total = ringkasan["baris_sheet_a"] + ringkasan["baris_kalender"]
    db.catat_run(conn, "SYNC", periode_run, total, db.STATUS_SUKSES, catatan=str(ringkasan))
    console.print(
        f"[green]OK[/green] Sheet A: {ringkasan['baris_sheet_a']} baris, "
        f"Kalender Rilis: {ringkasan['baris_kalender']} baris "
        f"({ringkasan['kolom_manual_dibaca_balik']} isian manual dibaca balik ke SQLite)."
    )
    conn.close()


@app.command()
def status():
    """Ringkasan run terakhir per sumber + minggu yang bolong. Perintah paling sering dipakai."""
    conn = _sambung()

    try:
        cfg = muat_config(_config_path())
    except ConfigError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    tabel = Table(title="Status Radar Tren Desain")
    tabel.add_column("Sumber")
    tabel.add_column("Periode terakhir")
    tabel.add_column("Status terakhir")
    tabel.add_column("Jumlah baris")
    tabel.add_column("Total run")

    ada_bolong = False

    for sumber in SUMBER_MINGGUAN:
        log = db.ambil_run_log(conn, sumber)
        if not log:
            tabel.add_row(sumber, "-", "[yellow]belum pernah jalan[/yellow]", "-", "0")
            continue

        terakhir = log[-1]
        periode_awal = log[0]["periode"]
        periode_akhir = terakhir["periode"]
        semua_periode_diharapkan = daftar_periode_antara(periode_awal, min(periode_akhir, periode_sekarang()))
        periode_tercatat = {row["periode"] for row in log}
        bolong = [p for p in semua_periode_diharapkan if p not in periode_tercatat]

        warna_status = {
            db.STATUS_SUKSES: "green",
            db.STATUS_GAGAL: "red",
            db.STATUS_KOSONG: "yellow",
            db.STATUS_DILEWATI: "cyan",
        }.get(terakhir["status"], "white")

        tabel.add_row(
            sumber,
            terakhir["periode"],
            f"[{warna_status}]{terakhir['status']}[/{warna_status}]",
            str(terakhir["jumlah_baris"]),
            str(len(log)),
        )
        if bolong:
            ada_bolong = True
            console.print(f"[red]PERINGATAN {sumber}: minggu BOLONG (tidak tercatat sama sekali): {', '.join(bolong)}[/red]")

    console.print(tabel)

    if not ada_bolong:
        console.print("[green]Tidak ada minggu yang bolong untuk sumber mingguan.[/green]")

    if date.today() >= cfg.dikunci_sampai:
        console.print(
            f"[yellow]PERINGATAN: dikunci_sampai ({cfg.dikunci_sampai}) sudah lewat -- waktunya review daftar "
            "kata_pantau bersama Denny.[/yellow]"
        )
    else:
        console.print(f"Kata pantau terkunci sampai {cfg.dikunci_sampai}.")

    kalender_log = db.ambil_run_log(conn, "ANILIST")
    if kalender_log:
        console.print(f"Kalender (ANILIST): run terakhir periode {kalender_log[-1]['periode']}, "
                       f"status {kalender_log[-1]['status']}.")
    else:
        console.print("[yellow]Kalender (ANILIST): belum pernah dijalankan.[/yellow]")

    conn.close()


@app.command()
def lewati(
    sumber: str = typer.Option(..., "--sumber"),
    periode: str = typer.Option(..., "--periode"),
    alasan: str = typer.Option(..., "--alasan"),
):
    """Catat satu periode sengaja dilewati (bukan lubang data diam-diam)."""
    conn = _sambung()
    db.catat_run(conn, sumber.upper(), periode, 0, db.STATUS_DILEWATI, catatan=alasan)
    console.print(f"[cyan]Dicatat: {sumber.upper()} periode {periode} DILEWATI -- {alasan}[/cyan]")
    conn.close()


if __name__ == "__main__":
    app()
