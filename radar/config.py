"""Baca & validasi config/kata_pantau.yaml, tegakkan aturan dikunci_sampai."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml


class ConfigError(Exception):
    pass


class KataPantauTerkunciError(Exception):
    """Daftar kata_pantau berubah sebelum tanggal dikunci_sampai."""


@dataclass
class KataPantauConfig:
    versi: int
    dikunci_sampai: date
    region_utama: str
    kata_pantau: list[str]
    path: Path


def muat_config(path: str | Path) -> KataPantauConfig:
    p = Path(path)
    if not p.exists():
        raise ConfigError(
            f"File config tidak ditemukan: {p}. "
            "Jalankan 'radar init' dulu atau cek RADAR_CONFIG_PATH."
        )
    with p.open("r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"Gagal parse YAML di {p}: {e}") from e

    if not isinstance(data, dict):
        raise ConfigError(f"Isi {p} bukan mapping YAML yang valid.")

    wajib = ["versi", "dikunci_sampai", "region_utama", "kata_pantau"]
    hilang = [k for k in wajib if k not in data]
    if hilang:
        raise ConfigError(f"Kolom wajib hilang di {p}: {', '.join(hilang)}")

    kata_pantau = data["kata_pantau"]
    if not isinstance(kata_pantau, list) or not all(isinstance(x, str) for x in kata_pantau):
        raise ConfigError(f"'kata_pantau' di {p} harus berupa list string.")
    if not (1 <= len(kata_pantau) <= 30):
        raise ConfigError(
            f"'kata_pantau' berisi {len(kata_pantau)} istilah -- brief mensyaratkan 10-15."
        )

    dikunci_sampai = data["dikunci_sampai"]
    if isinstance(dikunci_sampai, str):
        dikunci_sampai = date.fromisoformat(dikunci_sampai)
    elif not isinstance(dikunci_sampai, date):
        raise ConfigError(f"'dikunci_sampai' di {p} harus tanggal ISO (YYYY-MM-DD).")

    return KataPantauConfig(
        versi=int(data["versi"]),
        dikunci_sampai=dikunci_sampai,
        region_utama=str(data["region_utama"]),
        kata_pantau=kata_pantau,
        path=p,
    )


def _snapshot(cfg: KataPantauConfig) -> str:
    return json.dumps(sorted(cfg.kata_pantau), ensure_ascii=False)


def tegakkan_kunci(cfg: KataPantauConfig, ambil_meta, set_meta, hari_ini: date | None = None) -> None:
    """Bandingkan kata_pantau saat ini dengan snapshot tersimpan di DB.

    ambil_meta(key) -> str | None
    set_meta(key, value) -> None

    Kalau belum ada snapshot, simpan snapshot sekarang (baseline, biasanya saat 'radar init').
    Kalau sudah ada dan berbeda, dan hari ini masih sebelum dikunci_sampai -> tolak jalan.
    """
    hari_ini = hari_ini or date.today()
    snapshot_lama = ambil_meta("kata_pantau_snapshot")
    snapshot_baru = _snapshot(cfg)

    if snapshot_lama is None:
        set_meta("kata_pantau_snapshot", snapshot_baru)
        return

    if snapshot_lama == snapshot_baru:
        return

    if hari_ini < cfg.dikunci_sampai:
        raise KataPantauTerkunciError(
            f"Daftar kata_pantau di {cfg.path} berubah, tapi masih terkunci sampai "
            f"{cfg.dikunci_sampai.isoformat()} (hari ini {hari_ini.isoformat()}). "
            "Data antar-minggu tidak bisa dibandingkan kalau kata pantau berubah-ubah. "
            "Kembalikan daftar semula, atau kalau perubahan ini disengaja, jalankan "
            "'radar init --terima-perubahan-kata-pantau' untuk menyimpan baseline baru."
        )

    # Sudah lewat tanggal kunci -- izinkan, tapi perbarui snapshot supaya tidak nyangkut.
    set_meta("kata_pantau_snapshot", snapshot_baru)
