"""
apiloader.py
=============
Stage 1 of the tidal pipeline: read raw feed data from the ThingSpeak REST API.

Important
---------
ThingSpeak returns at most 8000 feed rows per request. A fixed 14-day request
can therefore silently lose the earliest rows when the sensor logs frequently
(e.g. every 1 minute). ``fetch_range`` below prevents that by recursively
splitting any time window that returns 8000 rows until every sub-window is
below the API cap. The final frames are concatenated and de-duplicated.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
import requests

import config

logger = logging.getLogger(__name__)

THINGSPEAK_MAX_RESULTS = 8000


@dataclass
class ThingSpeakConfig:
    """Everything needed to address one ThingSpeak channel/field set."""

    channel_id: int
    read_api_key: str
    field_map: dict[int, str] = field(default_factory=dict)
    base_url: str = config.THINGSPEAK_BASE_URL


class ThingSpeakAPILoader:
    """Thin reusable client for reading feed data from one ThingSpeak channel."""

    def __init__(self, cfg: ThingSpeakConfig, session: Optional[requests.Session] = None):
        self.config = cfg
        self.session = session or requests.Session()

    def _endpoint(self) -> str:
        return f"{self.config.base_url}/channels/{self.config.channel_id}/feeds.json"

    def _empty_frame(self) -> pd.DataFrame:
        cols = ["created_at", "entry_id", *self.config.field_map.values()]
        return pd.DataFrame(columns=cols)

    def _rename_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        rename = {f"field{k}": v for k, v in self.config.field_map.items()}
        return df.rename(columns=rename)

    def fetch(
        self,
        results: Optional[int] = 8000,
        start: Optional[str] = None,
        end: Optional[str] = None,
        timeout: float = 15.0,
    ) -> pd.DataFrame:
        """Fetch one ThingSpeak response (maximum 8000 rows)."""
        params: dict[str, object] = {"api_key": self.config.read_api_key}
        if start and end:
            params["start"] = start
            params["end"] = end
        else:
            params["results"] = min(results or THINGSPEAK_MAX_RESULTS, THINGSPEAK_MAX_RESULTS)

        logger.info(
            "Fetching ThingSpeak feed: channel=%s params=%s",
            self.config.channel_id,
            {k: v for k, v in params.items() if k != "api_key"},
        )
        response = self.session.get(self._endpoint(), params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()

        feeds = payload.get("feeds", [])
        if not feeds:
            logger.warning("ThingSpeak returned no feed entries for this request.")
            return self._empty_frame()

        return self._rename_fields(pd.DataFrame(feeds))

    def _fetch_complete_window(
        self,
        start_ts: pd.Timestamp,
        end_ts: pd.Timestamp,
        pause_seconds: float,
        timeout: float,
        depth: int = 0,
        max_depth: int = 24,
        min_window: pd.Timedelta = pd.Timedelta(seconds=2),
    ) -> list[pd.DataFrame]:
        """Fetch one window completely, splitting it if the 8000-row cap is hit.

        A response with exactly 8000 rows is treated as potentially truncated.
        The window is bisected and each half is fetched independently. Boundary
        duplicates are harmless because ``fetch_range`` later de-duplicates by
        ``entry_id``.
        """
        frame = self.fetch(
            start=start_ts.strftime("%Y-%m-%d %H:%M:%S"),
            end=end_ts.strftime("%Y-%m-%d %H:%M:%S"),
            timeout=timeout,
        )

        if len(frame) < THINGSPEAK_MAX_RESULTS:
            return [frame]

        window = end_ts - start_ts
        if depth >= max_depth or window <= min_window:
            raise RuntimeError(
                "ThingSpeak masih mengembalikan 8000 record pada jendela yang "
                f"sangat kecil ({start_ts} s.d. {end_ts}). Tidak aman untuk "
                "melanjutkan karena data mungkin terpotong."
            )

        midpoint = start_ts + (window / 2)
        midpoint = midpoint.floor("s")
        if midpoint <= start_ts or midpoint >= end_ts:
            raise RuntimeError(
                "Tidak dapat membagi jendela ThingSpeak lebih kecil lagi: "
                f"{start_ts} s.d. {end_ts}."
            )

        logger.warning(
            "Window %s s.d. %s mencapai limit %d record; "
            "memecah otomatis pada %s agar data awal tidak hilang.",
            start_ts,
            end_ts,
            THINGSPEAK_MAX_RESULTS,
            midpoint,
        )
        if pause_seconds > 0:
            time.sleep(pause_seconds)

        left = self._fetch_complete_window(
            start_ts,
            midpoint,
            pause_seconds=pause_seconds,
            timeout=timeout,
            depth=depth + 1,
            max_depth=max_depth,
            min_window=min_window,
        )
        if pause_seconds > 0:
            time.sleep(pause_seconds)
        right = self._fetch_complete_window(
            midpoint,
            end_ts,
            pause_seconds=pause_seconds,
            timeout=timeout,
            depth=depth + 1,
            max_depth=max_depth,
            min_window=min_window,
        )
        return left + right

    def fetch_range(
        self,
        start: str,
        end: str,
        chunk: str = "14D",
        pause_seconds: float = 0.2,
        timeout: float = 15.0,
    ) -> pd.DataFrame:
        """Fetch the complete requested date range without silent 8000-row loss.

        ``chunk`` is only the initial request-window size. If any initial chunk
        reaches ThingSpeak's 8000-row response cap, it is recursively split
        until every returned sub-window contains fewer than 8000 rows.
        """
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        if pd.isna(start_ts) or pd.isna(end_ts):
            raise ValueError("start/end ThingSpeak tidak dapat dibaca sebagai datetime.")
        if end_ts <= start_ts:
            raise ValueError("end harus lebih besar dari start.")

        offset = pd.tseries.frequencies.to_offset(chunk)
        frames: list[pd.DataFrame] = []
        window_start = start_ts

        while window_start < end_ts:
            window_end = min(window_start + offset, end_ts)
            frames.extend(
                self._fetch_complete_window(
                    window_start,
                    window_end,
                    pause_seconds=pause_seconds,
                    timeout=timeout,
                )
            )
            window_start = window_end
            if pause_seconds > 0 and window_start < end_ts:
                time.sleep(pause_seconds)

        if not frames:
            return self._empty_frame()

        combined = pd.concat(frames, ignore_index=True)
        if combined.empty:
            return self._empty_frame()

        if "entry_id" in combined.columns:
            combined = combined.drop_duplicates(subset="entry_id", keep="first")
        elif "created_at" in combined.columns:
            combined = combined.drop_duplicates(subset="created_at", keep="first")

        if "created_at" in combined.columns:
            sort_key = pd.to_datetime(combined["created_at"], errors="coerce", utc=True)
            combined = (
                combined.assign(_sort_time=sort_key)
                .sort_values("_sort_time", kind="stable")
                .drop(columns="_sort_time")
            )

        combined = combined.reset_index(drop=True)
        logger.info(
            "Complete ThingSpeak range fetched: requested=%s s.d. %s | rows=%d | returned=%s s.d. %s",
            start,
            end,
            len(combined),
            combined["created_at"].iloc[0] if "created_at" in combined.columns and len(combined) else "-",
            combined["created_at"].iloc[-1] if "created_at" in combined.columns and len(combined) else "-",
        )
        return combined


def default_loader() -> ThingSpeakAPILoader:
    """Loader pre-configured for the Ultrasonic Tide channel via config.py."""
    cfg = ThingSpeakConfig(
        channel_id=config.THINGSPEAK_CHANNEL_ID,
        read_api_key=config.THINGSPEAK_READ_API_KEY,
        field_map=config.FIELD_MAP,
    )
    return ThingSpeakAPILoader(cfg)


def load_latest(results: int = 8000) -> pd.DataFrame:
    """Fetch the most recent ``results`` entries."""
    return default_loader().fetch(results=results)


def load_period(start: str, end: str, chunk: str = "14D") -> pd.DataFrame:
    """Fetch the COMPLETE date range with automatic anti-truncation splitting."""
    return default_loader().fetch_range(start=start, end=end, chunk=chunk)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raw = load_latest(results=100)
    print(raw.head())
    print(f"\n{len(raw)} rows fetched.")
