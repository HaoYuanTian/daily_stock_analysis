from unittest.mock import Mock, patch

import pandas as pd

from data_provider.hithink_fetcher import HithinkFetcher
from src.search_service import SearchResponse, SearchService


def test_history_preserves_shanghai_dates_and_share_units():
    fetcher = HithinkFetcher("test")
    date = pd.Timestamp("2026-11-19", tz="Asia/Shanghai")
    bar = dict(date_ms=date.value // 1_000_000, open_price=10, high_price=11, low_price=9,
               close_price=11, volume=50123, turnover=501230)
    with patch.object(fetcher.client, "instrument", return_value={"thscode": "002992.SZ", "asset_type": "a-share"}), \
         patch.object(fetcher.client, "get", return_value={"item": [bar]}) as request:
        bars = fetcher.get_daily_data("002992", "2026-11-19", "2026-11-19")
    assert request.call_args.kwargs["adjust"] == "forward"
    assert bars.loc[0, "date"] == date.tz_localize(None)
    assert bars.loc[0, "volume"] == 50123
    assert pd.isna(bars.loc[0, "pct_chg"])


def test_timeline_without_recent_items_uses_configured_web_search():
    service = SearchService(hithink_api_key="test")
    provider = Mock()
    service._providers = [provider]
    response = SearchResponse("query", [], "fallback")
    provider.search.return_value = response
    with patch.object(service.hithink, "stock", return_value={"thscode": "002992.SZ"}), \
         patch.object(service.hithink, "get", return_value={"items": [{"title": "old", "publish_time_ms": 1000}]}):
        result = service.search_comprehensive_intel("002992", "宝明科技", max_searches=1)
    assert result["latest_news"] is response
    provider.search.assert_called_once()


def test_etf_history_and_quote_use_fund_market_endpoints():
    fetcher = HithinkFetcher("test")
    instrument = {"thscode": "512000.SH", "asset_type": "fund-etf", "name": "证券ETF"}
    quote = {"thscode": "512000.SH", "last_price": 1.23, "volume": 12300, "turnover_ratio_pct": 2.5}
    with patch.object(fetcher.client, "instrument", return_value=instrument), \
         patch.object(fetcher.client, "get", side_effect=[dict(thscode="512000.SH", item=[]), dict(item=[quote])]) as get:
        assert fetcher._fetch_raw_data("512000", "2026-11-16", "2026-11-19").empty
        result = fetcher.get_realtime_quote("512000")
    history, snapshot = get.call_args_list
    assert history.args == ("fund/market/historical",)
    assert history.kwargs["thscode"] == "512000.SH" and "adjust" not in history.kwargs
    assert snapshot.args == ("fund/market/snapshot",) and snapshot.kwargs == {"thscode": "512000.SH"}
    assert (result.price, result.volume, result.turnover_rate) == (1.23, 123, 2.5)
