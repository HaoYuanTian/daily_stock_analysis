from unittest.mock import Mock, patch

import pandas as pd

from data_provider.hithink_fetcher import HithinkFetcher
from src.search_service import SearchResponse, SearchService


def test_history_preserves_shanghai_dates_and_share_units():
    fetcher = HithinkFetcher("test")
    date = pd.Timestamp("2026-11-19", tz="Asia/Shanghai")
    bar = dict(date_ms=date.value // 1_000_000, open_price=10, high_price=11, low_price=9,
               close_price=11, volume=50123, turnover=501230)
    with patch.object(fetcher.client, "stock", return_value={"thscode": "002992.SZ"}), \
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
