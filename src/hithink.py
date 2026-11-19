"""Client for the public Hithink Finance REST API."""

from functools import lru_cache
from zoneinfo import ZoneInfo

import requests

SHANGHAI = ZoneInfo("Asia/Shanghai")


class HithinkClient:
    def __init__(self, api_key: str):
        self._api_key = api_key

    def get(self, path: str, **params) -> dict:
        response = requests.get(
            f"https://fuyao.aicubes.cn/api/{path}",
            headers={"X-api-key": self._api_key},
            params=params,
            timeout=(4, 10),
            allow_redirects=False,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0 or not isinstance(payload.get("data"), dict):
            raise ValueError(f"Hithink {path}: code={payload.get('code')}, request_id={payload.get('request_id')}")
        return payload["data"]

    @lru_cache(maxsize=512)
    def stock(self, ticker: str):
        """Resolve only exact A-share matches; funds and overseas symbols use their own providers."""
        if not (len(ticker) == 6 and ticker.isascii() and ticker.isdigit()):
            return None
        rows = self.get("meta/tickers/search", q=ticker, asset_type="a-share")["item"]
        matches = [r for r in rows if r.get("ticker") == ticker and r.get("asset_type") == "a-share" and r.get("thscode")]
        return matches[0] if len(matches) == 1 else None
