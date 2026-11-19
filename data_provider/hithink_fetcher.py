"""Hithink mainland stock and ETF prices and mainland benchmark quotes."""

import pandas as pd

from src.hithink import SHANGHAI, HithinkClient

from .base import STANDARD_COLUMNS, BaseFetcher, DataFetchError
from .realtime_types import RealtimeSource, UnifiedRealtimeQuote


class HithinkFetcher(BaseFetcher):
    name = "HithinkFetcher"
    priority = -2

    def __init__(self, api_key: str):
        self.client = HithinkClient(api_key)

    def _fetch_raw_data(self, stock_code, start_date, end_date):
        instrument = self.client.instrument(stock_code, "a-share,fund-etf")
        if not instrument:
            raise DataFetchError(f"No Hithink stock or ETF match for {stock_code}")
        start = pd.Timestamp(start_date, tz=SHANGHAI)
        end = pd.Timestamp(end_date, tz=SHANGHAI) + pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1)
        params = dict(thscode=instrument["thscode"], interval="1d",
                      start=start.value // 1_000_000, end=end.value // 1_000_000)
        if instrument["asset_type"] == "fund-etf":
            data = self.client.get("fund/market/historical", **params)
            if data.get("thscode") != instrument["thscode"]:
                raise DataFetchError(f"Unexpected Hithink ETF history for {stock_code}")
        else:
            data = self.client.get("a-share/prices/historical", adjust="forward", **params)
        return pd.DataFrame(data["item"])

    def _normalize_data(self, df, stock_code):
        bars = df.rename(columns={
            "open_price": "open", "high_price": "high", "low_price": "low",
            "close_price": "close", "turnover": "amount",
        }).copy()
        bars["date"] = pd.to_datetime(bars["date_ms"], unit="ms", utc=True).dt.tz_convert(SHANGHAI).dt.tz_localize(None)
        bars = bars.dropna(subset=["date", "open", "high", "low", "close", "volume"]).sort_values("date")
        bars["pct_chg"] = pd.to_numeric(bars["close"]).pct_change(fill_method=None) * 100
        return bars[STANDARD_COLUMNS]

    def get_realtime_quote(self, stock_code):
        instrument = self.client.instrument(stock_code, "a-share,fund-etf")
        if not instrument:
            return None
        if instrument["asset_type"] == "fund-etf":
            snapshot = self.client.get("fund/market/snapshot", thscode=instrument["thscode"])
        else:
            snapshot = self.client.get("a-share/prices/snapshot", thscodes=instrument["thscode"])
        rows = snapshot["item"]
        for row in rows:
            if row.get("thscode") == instrument["thscode"] and (row.get("last_price") or 0) > 0:
                volume = row.get("volume")
                return UnifiedRealtimeQuote(
                    code=stock_code, name=instrument.get("name") or "", source=RealtimeSource.HITHINK,
                    price=row["last_price"], change_pct=row.get("price_change_ratio_pct"),
                    change_amount=row.get("price_change"), amount=row.get("turnover"),
                    volume=int(volume // 100) if volume is not None else None,
                    amplitude=row.get("price_amplitude_ratio_pct"), turnover_rate=row.get("turnover_ratio_pct"),
                    open_price=row.get("open_price"), high=row.get("high_price"),
                    low=row.get("low_price"), pre_close=row.get("prev_price"),
                )
        return None

    def get_main_indices(self, region="cn"):
        if region != "cn":
            return None
        names = {
            "000001.SH": "上证指数", "399001.SZ": "深证成指", "399006.SZ": "创业板指",
            "000688.SH": "科创50", "000016.SH": "上证50", "000300.SH": "沪深300",
        }
        data = self.client.get("a-share-index/prices/snapshot", thscodes=",".join(names))
        rows = {row["thscode"]: row for row in data["item"]}
        indices = []
        for code, name in names.items():
            row = rows.get(code)
            if not row or not row.get("last_price") or row.get("price_change_ratio_pct") is None:
                return None
            high, low, prev = row.get("high_price"), row.get("low_price"), row.get("prev_price")
            amplitude = (high - low) / prev * 100 if high is not None and low is not None and prev else None
            indices.append({
                "code": code.split(".")[0], "name": name, "current": row["last_price"], "change": row.get("price_change"),
                "change_pct": row["price_change_ratio_pct"], "open": row.get("open_price"), "high": high, "low": low,
                "prev_close": prev, "volume": row.get("volume"), "amount": row.get("turnover"), "amplitude": amplitude,
            })
        return indices
