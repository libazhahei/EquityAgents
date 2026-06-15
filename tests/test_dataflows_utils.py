import pandas as pd

from tradingagents.dataflows.utils import market_briefing


def test_market_briefing_structure_stats_with_date_column():
    df = pd.DataFrame(
        {
            "Date": [
                "2026-06-01",
                "2026-06-02",
                "2026-06-03",
                "2026-06-04",
                "2026-06-07",
                "2026-06-08",
            ],
            "Open": [100, 101, 102, 101, 103, 104],
            "High": [101, 102, 103, 103, 105, 106],
            "Low": [99, 100, 101, 100, 102, 103],
            "Close": [100, 102, 101, 103, 104, 105],
            "Volume": [1000, 1100, 1050, 1200, 1300, 1400],
        }
    )

    result = market_briefing("structure_stats", df)
    assert "Current trend state" in result
    assert "Recent swing highs" in result
    assert "BOS events" in result


def test_market_briefing_structure_stats_with_int_index():
    df = pd.DataFrame(
        {
            "Open": [100, 102, 101, 103, 104, 105],
            "High": [101, 103, 102, 104, 105, 106],
            "Low": [99, 101, 100, 102, 103, 104],
            "Close": [100, 102, 101, 103, 104, 105],
            "Volume": [1000, 1100, 1050, 1200, 1300, 1400],
        }
    )

    result = market_briefing("structure_stats", df)
    assert "Current trend state" in result
    assert "Recent swing highs" in result
    assert "BOS events" in result


def test_market_briefing_pattern_stats_with_int_index():
    df = pd.DataFrame(
        {
            "Open": [100, 102, 101, 103, 104, 105],
            "High": [101, 103, 102, 104, 105, 106],
            "Low": [99, 101, 100, 102, 103, 104],
            "Close": [100, 102, 101, 103, 104, 105],
            "Volume": [1000, 1100, 1050, 1200, 1300, 1400],
        }
    )

    result = market_briefing("pattern_stats", df)
    assert "Most recent signals" in result
    assert "No significant reversal patterns" not in result
