"""Klien AniList GraphQL -- satu-satunya sumber dengan API resmi (Bab 5.3 brief).

Gratis, tanpa autentikasi, tapi ada rate limit. Kolom status_ip dan
lini_hog_relevan SENGAJA tidak diisi di sini -- itu diisi manusia.
"""

from __future__ import annotations

import json
import time
from datetime import date

import httpx

from radar.models import KalenderRilis

ANILIST_URL = "https://graphql.anilist.co"
MUSIM_VALID = ["WINTER", "SPRING", "SUMMER", "FALL"]

QUERY = """
query ($season: MediaSeason, $seasonYear: Int, $page: Int) {
  Page(page: $page, perPage: 50) {
    pageInfo { hasNextPage }
    media(season: $season, seasonYear: $seasonYear, type: ANIME, sort: POPULARITY_DESC) {
      id
      title { romaji english }
      startDate { year month day }
      popularity
      favourites
      genres
    }
  }
}
"""


class AniListError(Exception):
    pass


class AniListAdapter:
    nama = "ANILIST"

    def __init__(self, client: httpx.Client | None = None, max_percobaan: int = 3):
        self._client = client or httpx.Client(timeout=30.0)
        self._own_client = client is None
        self.max_percobaan = max_percobaan

    def __del__(self):
        if getattr(self, "_own_client", False):
            try:
                self._client.close()
            except Exception:
                pass

    def _panggil(self, variables: dict) -> dict:
        percobaan = 0
        while True:
            percobaan += 1
            resp = self._client.post(ANILIST_URL, json={"query": QUERY, "variables": variables})
            if resp.status_code == 429:
                if percobaan >= self.max_percobaan:
                    raise AniListError("AniList membalas 429 (rate limited) berulang kali.")
                tunggu = float(resp.headers.get("Retry-After", "5"))
                time.sleep(tunggu)
                continue
            if resp.status_code >= 400:
                raise AniListError(f"AniList membalas HTTP {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            if "errors" in data and data["errors"]:
                raise AniListError(f"AniList mengembalikan error: {data['errors']}")
            return data["data"]

    def ambil_musim(self, musim: str, tahun: int) -> list[KalenderRilis]:
        musim = musim.upper()
        if musim not in MUSIM_VALID:
            raise ValueError(f"--musim harus salah satu dari {MUSIM_VALID}, dapat {musim!r}")

        hasil: list[KalenderRilis] = []
        page = 1
        while True:
            data = self._panggil({"season": musim, "seasonYear": tahun, "page": page})
            page_data = data["Page"]
            for m in page_data["media"]:
                sd = m.get("startDate") or {}
                if not sd.get("year") or not sd.get("month") or not sd.get("day"):
                    continue  # tanggal_rilis wajib -- lewati entri tanpa tanggal lengkap
                tanggal_rilis = date(sd["year"], sd["month"], sd["day"])
                judul = (m["title"].get("english") or m["title"].get("romaji") or "").strip()
                if not judul:
                    continue
                genres = m.get("genres") or []
                hasil.append(
                    KalenderRilis(
                        tanggal_rilis=tanggal_rilis,
                        kategori="ANIME",
                        judul=judul,
                        perkiraan_minat=float(m["popularity"]) if m.get("popularity") is not None else None,
                        sumber=self.nama,
                        raw=json.dumps(m, ensure_ascii=False),
                        catatan=", ".join(genres) if genres else None,
                    )
                )
            if not page_data["pageInfo"]["hasNextPage"]:
                break
            page += 1
            time.sleep(0.5)  # hormati rate limit AniList
        return hasil
