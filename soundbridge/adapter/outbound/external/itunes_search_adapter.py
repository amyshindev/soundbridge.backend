# 레이어: Outbound — iTunes Search API (정식 발매 곡 자동완성)
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"


class ItunesSearchAdapter:
    """Apple iTunes Search API — API 키 불필요, KR 스토어 기준."""

    async def search_songs(
        self,
        query: str,
        *,
        limit: int = 8,
        country: str = "KR",
    ) -> list[dict]:
        term = query.strip()
        if not term:
            return []

        params = {
            "term": term,
            "entity": "song",
            "media": "music",
            "limit": min(limit, 25),
            "country": country,
            "lang": "ko_kr",
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(ITUNES_SEARCH_URL, params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as e:
            logger.warning("iTunes search failed for %r: %s", term, e)
            return []

        results: list[dict] = []
        seen: set[str] = set()

        for item in payload.get("results", []):
            track_id = item.get("trackId")
            title = (item.get("trackName") or "").strip()
            artist = (item.get("artistName") or "").strip()
            if not track_id or not title or not artist:
                continue

            dedupe_key = f"{artist.lower()}|{title.lower()}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            artwork = item.get("artworkUrl100") or item.get("artworkUrl60") or ""
            if artwork:
                artwork = artwork.replace("100x100bb", "60x60bb")

            results.append(
                {
                    "id": str(track_id),
                    "title": title,
                    "artist": artist,
                    "album": (item.get("collectionName") or "").strip(),
                    "artwork_url": artwork,
                    "display": f"{artist} — {title}",
                }
            )

            if len(results) >= limit:
                break

        return results
