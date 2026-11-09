"""
apiloader.py
=============
Stage 1 of the tidal pipeline: talk to the ThingSpeak REST API and hand
back the raw feed data as a DataFrame.

Design notes
------------
* This module knows nothing about tides, quality control, or
  interpolation -- that's preprocessing.py's job. It only knows how to
  ask ThingSpeak for feed rows and hand back what it received. Keeping
  the boundary here means apiloader.py is reusable for *any* ThingSpeak
  channel/field, not just this one, and preprocessing.py can be tested
  with fixture data without ever hitting the network.
* ThingSpeak caps a single `/feeds.json` request at 8000 entries. For
  anything longer than that, `fetch_range()` below pages through the
  channel by splitting the requested period into chunks.
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

THINGSPEAK_MAX_RESULTS = 8000  # hard limit imposed by the ThingSpeak API


@dataclass
class ThingSpeakConfig:
    """Everything needed to address one ThingSpeak channel/field set."""

    channel_id: int
    read_api_key: str
    field_map: dict[int, str] = field(default_factory=dict)  # {1: "tide_swl"}
    base_url: str = config.THINGSPEAK_BASE_URL


class ThingSpeakAPILoader:
    """Thin, reusable client for reading feed data from one ThingSpeak channel."""

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
        """
        Fetch feed entries once (single request, up to 8000 rows).

        Parameters
        ----------
        results : int, optional
            Number of most-recent entries to fetch. Ignored if both
            `start` and `end` are given.
        start, end : str, optional
            "YYYY-MM-DD HH:MM:SS" bounds (channel-local time as stored
            by ThingSpeak) passed straight through as the API's
            `start`/`end` query params.
        timeout : float
            Per-request timeout in seconds.

        Returns
        -------
        pd.DataFrame
            Raw rows exactly as returned by the API (renamed field<N>
            columns), with no cleaning, type-casting, or interpolation
            applied.
        """
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

    def fetch_range(
        self,
        start: str,
        end: str,
        chunk: str = "14D",
        pause_seconds: float = 0.2,
        timeout: float = 15.0,
    ) -> pd.DataFrame:
        """
        Fetch a date range longer than the API's per-request limit by
        paging through it in chunks and concatenating the results.

        Parameters
        ----------
        start, end : str
            "YYYY-MM-DD HH:MM:SS" bounds for the whole period wanted.
        chunk : str
            Pandas frequency/offset string for the size of each request
            window, e.g. "14D" for two-week chunks. Pick something small
            enough that no chunk is likely to contain >8000 samples at
            your sensor's logging rate.
        pause_seconds : float
            Delay between requests, to stay well under ThingSpeak's
            rate limits.

        Returns
        -------
        pd.DataFrame
            Concatenated raw rows across the whole period, de-duplicated
            on entry_id (chunk boundaries can otherwise overlap by one
            row).
        """
        bounds = pd.date_range(start=start, end=end, freq=chunk)
        if len(bounds) == 0 or bounds[-1] < pd.Timestamp(end):
            bounds = bounds.append(pd.DatetimeIndex([pd.Timestamp(end)]))
        if bounds[0] > pd.Timestamp(start):
            bounds = pd.DatetimeIndex([pd.Timestamp(start)]).append(bounds)

        frames = []
        for window_start, window_end in zip(bounds[:-1], bounds[1:]):
            frame = self.fetch(
                start=window_start.strftime("%Y-%m-%d %H:%M:%S"),
                end=window_end.strftime("%Y-%m-%d %H:%M:%S"),
                timeout=timeout,
            )
            frames.append(frame)
            time.sleep(pause_seconds)

        if not frames:
            return self._empty_frame()

        combined = pd.concat(frames, ignore_index=True)
        if "entry_id" in combined.columns:
            combined = combined.drop_duplicates(subset="entry_id")
        return combined.reset_index(drop=True)


def default_loader() -> ThingSpeakAPILoader:
    """Loader pre-configured for the 'Ultrasonic Tide' channel via config.py."""
    cfg = ThingSpeakConfig(
        channel_id=config.THINGSPEAK_CHANNEL_ID,
        read_api_key=config.THINGSPEAK_READ_API_KEY,
        field_map=config.FIELD_MAP,
    )
    return ThingSpeakAPILoader(cfg)


def load_latest(results: int = 8000) -> pd.DataFrame:
    """Convenience one-liner: fetch the most recent `results` entries."""
    return default_loader().fetch(results=results)


def load_period(start: str, end: str, chunk: str = "14D") -> pd.DataFrame:
    """Convenience one-liner: fetch a date range, paging automatically."""
    return default_loader().fetch_range(start=start, end=end, chunk=chunk)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raw = load_latest(results=100)
    print(raw.head())
    print(f"\n{len(raw)} rows fetched.")
