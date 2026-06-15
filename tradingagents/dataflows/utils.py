import re
from datetime import date, datetime, timedelta
from typing import Annotated

import pandas as pd

SavePathType = Annotated[str, "File path to save data. If None, data is not saved."]

# Tickers can contain letters, digits, dot, dash, underscore, caret
# (index symbols like ^GSPC), equals (futures like GC=F), and plus
# (forex/CFD symbols like XAUUSD+). None of these enable directory
# traversal, so the value never escapes a containing directory when
# interpolated into a path. Anything else is rejected.
_TICKER_PATH_RE = re.compile(r"^[A-Za-z0-9._\-\^=+]+$")


def safe_ticker_component(value: str, *, max_len: int = 32) -> str:
    """Validate ``value`` is safe to interpolate into a filesystem path.

    Tickers come from user CLI input or from LLM tool calls, both of which
    can be influenced by attacker-controlled content (e.g. prompt injection
    embedded in fetched news). Without validation, a value like
    ``"../../../etc/foo"`` flows into ``os.path.join`` / ``Path /`` and
    escapes the configured cache, checkpoint, or results directory.

    Returns ``value`` unchanged when it matches the allowed pattern; raises
    ``ValueError`` otherwise.
    """
    if not isinstance(value, str) or not value:
        raise ValueError(f"ticker must be a non-empty string, got {value!r}")
    if len(value) > max_len:
        raise ValueError(f"ticker exceeds {max_len} chars: {value!r}")
    if not _TICKER_PATH_RE.fullmatch(value):
        raise ValueError(
            f"ticker contains characters not allowed in a filesystem path: {value!r}"
        )
    # The regex above allows '.', so values like '.', '..', '...' would pass,
    # and as a path component they traverse the parent directory. Reject any
    # value that's only dots.
    if set(value) == {"."}:
        raise ValueError(f"ticker cannot consist solely of dots: {value!r}")
    return value


def save_output(data: pd.DataFrame, tag: str, save_path: SavePathType = None) -> None:
    if save_path:
        data.to_csv(save_path, encoding="utf-8")
        print(f"{tag} saved to {save_path}")


def get_current_date():
    return date.today().strftime("%Y-%m-%d")


def decorate_all_methods(decorator):
    def class_decorator(cls):
        for attr_name, attr_value in cls.__dict__.items():
            if callable(attr_value):
                setattr(cls, attr_name, decorator(attr_value))
        return cls

    return class_decorator


def get_next_weekday(date):

    if not isinstance(date, datetime):
        date = datetime.strptime(date, "%Y-%m-%d")

    if date.weekday() >= 5:
        days_to_add = 7 - date.weekday()
        next_weekday = date + timedelta(days=days_to_add)
        return next_weekday
    else:
        return date

def market_briefing(indicator: str, data: pd.DataFrame) -> str:
    """
    Generate a market briefing based on the specified indicator.
    Args:
        indicator (str): The market indicator to generate the briefing for, e.g. 'S&P 500', 'Dow Jones', 'NASDAQ'
        data (pd.DataFrame): The stock data to analyze.
    Returns:
        str: A market briefing report for the specified indicator.
    """
    from scipy.signal import argrelextrema
    from sklearn.cluster import KMeans
    import numpy as np
    # ─────────────────────────────────────────────
    # 1.  LOCAL EXTREMA + CLUSTERING → SUPPORT / RESISTANCE
    # ─────────────────────────────────────────────

    def _find_local_extrema(close: pd.Series, order: int = 5):
        """Return (peak_indices, trough_indices) using scipy argrelextrema."""
        arr = close.values
        peaks = argrelextrema(arr, np.greater_equal, order=order)[0]
        troughs = argrelextrema(arr, np.less_equal, order=order)[0]
        return peaks, troughs


    def _cluster_levels(prices: np.ndarray, n_clusters: int = 4) -> list[float]:
        """K-Means on 1-D price array → sorted cluster centres."""
        if len(prices) < n_clusters:
            return sorted(prices.tolist())
        km = KMeans(n_clusters=min(n_clusters, len(prices)), random_state=42, n_init=10)
        km.fit(prices.reshape(-1, 1))
        return sorted(km.cluster_centers_.flatten().tolist())


    def _normalize_close(close: pd.Series) -> pd.Series:
        close = pd.to_numeric(close, errors="coerce")
        if close.isna().any():
            close = close.ffill().bfill()
        if close.isna().any():
            raise ValueError("Close series contains too many invalid values to analyze.")
        return close


    def _support_resistance_section(close: pd.Series) -> str:
        close = _normalize_close(close)
        peaks_idx, troughs_idx = _find_local_extrema(close)
        peak_prices = close.iloc[peaks_idx].values if len(peaks_idx) else np.array([])
        trough_prices = close.iloc[troughs_idx].values if len(troughs_idx) else np.array([])

        lines = [f"  Local peaks found   : {len(peaks_idx)}",
                f"  Local troughs found : {len(troughs_idx)}"]

        if len(peak_prices) >= 2:
            resistance_levels = _cluster_levels(peak_prices)
            lines.append("  Key resistance zones (clustered peaks)  : " +
                        ", ".join(f"{v:.2f}" for v in resistance_levels))
        if len(trough_prices) >= 2:
            support_levels = _cluster_levels(trough_prices)
            lines.append("  Key support zones   (clustered troughs) : " +
                        ", ".join(f"{v:.2f}" for v in support_levels))

        return "\n".join(lines)


    # ─────────────────────────────────────────────
    # 2.  CANDLESTICK REVERSAL PATTERNS
    # ─────────────────────────────────────────────

    def _body(o, c):       return abs(c - o)
    def _upper_wick(o, h, c): return h - max(o, c)
    def _lower_wick(o, l, c): return min(o, c) - l
    def _is_bullish(o, c): return c > o
    def _is_bearish(o, c): return c < o


    def _detect_patterns(df: pd.DataFrame) -> list[tuple[str, str, str]]:
        """
        Returns list of (date_str, pattern_name, direction) tuples.
        direction: 'bullish' | 'bearish' | 'neutral'
        """
        results = []
        op, hi, lo, cl = (df["Open"].values, df["High"].values,
                        df["Low"].values, df["Close"].values)
        if "Date" in df.columns:
            dates = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("").tolist()
        elif isinstance(df.index, pd.DatetimeIndex):
            dates = df.index.strftime("%Y-%m-%d").tolist()
        else:
            dates = df.index.astype(str).tolist()
        n = len(df)

        for i in range(2, n):
            o, h, l, c = op[i], hi[i], lo[i], cl[i]
            po, ph, pl, pc = op[i - 1], hi[i - 1], lo[i - 1], cl[i - 1]
            ppo, pph, ppl, ppc = op[i - 2], hi[i - 2], lo[i - 2], cl[i - 2]
            body_size = _body(o, c)
            total_range = h - l if h != l else 1e-9
            low_wick = _lower_wick(o, l, c)
            up_wick = _upper_wick(o, h, c)

            # ── Single-candle ──────────────────────────────────────────────────
            # Hammer (bullish): small body near top, long lower wick
            if (low_wick >= 2 * body_size and up_wick <= 0.1 * total_range
                    and body_size / total_range <= 0.35 and _is_bullish(o, c)):
                results.append((dates[i], "Hammer", "bullish"))

            # Inverted Hammer / Shooting Star
            elif (up_wick >= 2 * body_size and low_wick <= 0.1 * total_range
                and body_size / total_range <= 0.35):
                tag = "Inverted Hammer" if _is_bullish(o, c) else "Shooting Star"
                direction = "bullish" if _is_bullish(o, c) else "bearish"
                results.append((dates[i], tag, direction))

            # Doji: very small body relative to range
            elif body_size / total_range < 0.05:
                results.append((dates[i], "Doji", "neutral"))

            # Pin Bar: body ≤ 25 % of range, wick on one side dominates
            elif (body_size / total_range <= 0.25 and
                (low_wick >= 2 * up_wick or up_wick >= 2 * low_wick)):
                direction = "bullish" if low_wick >= 2 * up_wick else "bearish"
                results.append((dates[i], "Pin Bar", direction))

            # Marubozu: almost no wicks
            elif (up_wick / total_range < 0.03 and low_wick / total_range < 0.03
                and body_size / total_range > 0.9):
                direction = "bullish" if _is_bullish(o, c) else "bearish"
                results.append((dates[i], "Marubozu", direction))

            # ── Two-candle ────────────────────────────────────────────────────
            # Bullish Engulfing
            if (_is_bearish(po, pc) and _is_bullish(o, c)
                    and o <= pc and c >= po):
                results.append((dates[i], "Bullish Engulfing", "bullish"))

            # Bearish Engulfing
            elif (_is_bullish(po, pc) and _is_bearish(o, c)
                and o >= pc and c <= po):
                results.append((dates[i], "Bearish Engulfing", "bearish"))

            # Tweezer Top (two high with matching highs)
            if abs(h - ph) / total_range < 0.02 and _is_bearish(o, c):
                results.append((dates[i], "Tweezer Top", "bearish"))

            # Tweezer Bottom
            elif abs(l - pl) / total_range < 0.02 and _is_bullish(o, c):
                results.append((dates[i], "Tweezer Bottom", "bullish"))

            # ── Three-candle ──────────────────────────────────────────────────
            # Morning Star
            if (_is_bearish(ppo, ppc) and _body(po, pc) / (ph - pl + 1e-9) < 0.3
                    and _is_bullish(o, c) and c > (ppo + ppc) / 2):
                results.append((dates[i], "Morning Star", "bullish"))

            # Evening Star
            elif (_is_bullish(ppo, ppc) and _body(po, pc) / (ph - pl + 1e-9) < 0.3
                and _is_bearish(o, c) and c < (ppo + ppc) / 2):
                results.append((dates[i], "Evening Star", "bearish"))

            # Three White Soldiers
            if (_is_bullish(ppo, ppc) and _is_bullish(po, pc) and _is_bullish(o, c)
                    and pc > ppc and c > pc):
                results.append((dates[i], "Three White Soldiers", "bullish"))

            # Three Black Crows
            elif (_is_bearish(ppo, ppc) and _is_bearish(po, pc) and _is_bearish(o, c)
                and pc < ppc and c < pc):
                results.append((dates[i], "Three Black Crows", "bearish"))

        return results


    def _patterns_section(df: pd.DataFrame) -> str:
        patterns = _detect_patterns(df)
        if not patterns:
            return "  No significant reversal patterns detected in the period."

        # Keep only the last ~10 and summarise counts
        counts: dict[str, dict[str, int]] = {}
        for _, name, direction in patterns:
            counts.setdefault(name, {"bullish": 0, "bearish": 0, "neutral": 0})
            counts[name][direction] += 1

        lines = []
        for name, cnt in sorted(counts.items()):
            parts = [f"{d}×{v}" for d, v in cnt.items() if v > 0]
            lines.append(f"  {name:<25} : {', '.join(parts)}")

        # Last 5 signals
        last5 = patterns[-5:]
        lines.append("  Most recent signals  : " +
                    " | ".join(f"{d}({p},{dir_})" for d, p, dir_ in last5))
        return "\n".join(lines)


    # ─────────────────────────────────────────────
    # 3.  VOLUME PROFILE  (Price-Binned Approximate "Chip Distribution")
    # ─────────────────────────────────────────────

    def _build_volume_profile(df: pd.DataFrame, n_bins: int = 40
                            ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Core calculation: distribute each day's Volume across price bins it touches.

        Weight rule: uniform across all bins the candle's [Low, High] spans,
        scaled by the fraction of the total range each bin represents.

        Returns
        -------
        bin_edges  : shape (n_bins+1,)
        bin_prices : shape (n_bins,)  — midpoint of each bin
        bin_vols   : shape (n_bins,)  — accumulated volume per bin
        """
        price_lo = df["Low"].min()
        price_hi = df["High"].max()
        if price_hi == price_lo:
            price_hi = price_lo * 1.01

        bin_edges = np.linspace(price_lo, price_hi, n_bins + 1)
        bin_prices = (bin_edges[:-1] + bin_edges[1:]) / 2
        bin_vols = np.zeros(n_bins)
        bin_width = bin_edges[1] - bin_edges[0]

        for _, row in df.iterrows():
            lo, hi, vol = row["Low"], row["High"], row["Volume"]
            if vol == 0 or hi == lo:
                continue
            candle_range = hi - lo

            # Find which bins overlap with [lo, hi]
            first_bin = max(0, int((lo - price_lo) / bin_width))
            last_bin  = min(n_bins - 1, int((hi - price_lo) / bin_width))

            for b in range(first_bin, last_bin + 1):
                b_lo = bin_edges[b]
                b_hi = bin_edges[b + 1]
                overlap = min(hi, b_hi) - max(lo, b_lo)
                if overlap > 0:
                    weight = overlap / candle_range
                    bin_vols[b] += vol * weight

        return bin_edges, bin_prices, bin_vols


    def _volume_profile_section(df: pd.DataFrame,
                                n_bins: int = 36,
                                bar_width: int = 28,
                                top_n: int = 5) -> str:
        """
        Build a text-art volume profile histogram + key analytics:
        - POC  (Point of Control)  : single highest-volume bin
        - VAH / VAL                : Value Area High / Low  (70 % of total volume)
        - HVN  (High Volume Nodes) : top-N dense clusters
        - LVN  (Low Volume Nodes)  : sparse price gaps
        - Current price vs VA      : position context
        """
        if "Volume" not in df.columns or df["Volume"].sum() == 0:
            return "  Volume data unavailable."

        _, bin_prices, bin_vols = _build_volume_profile(df, n_bins=n_bins)

        total_vol = bin_vols.sum()
        poc_idx   = int(np.argmax(bin_vols))
        poc_price = bin_prices[poc_idx]
        poc_vol   = bin_vols[poc_idx]

        # ── Value Area: accumulate 70 % of volume around POC ──────────────
        sorted_idx = np.argsort(bin_vols)[::-1]
        cumvol = 0.0
        va_bins: set[int] = set()
        for idx in sorted_idx:
            cumvol += bin_vols[idx]
            va_bins.add(idx)
            if cumvol >= 0.70 * total_vol:
                break
        va_indices = sorted(va_bins)
        vah = bin_prices[max(va_indices)]
        val = bin_prices[min(va_indices)]

        # ── HVN: top_n bins by volume (excluding POC itself) ──────────────
        hvn_indices = [i for i in sorted_idx[1: top_n + 1]]
        hvn_prices  = sorted(bin_prices[i] for i in hvn_indices)

        # ── LVN: bins whose volume < 5 % of POC volume ────────────────────
        lvn_threshold = 0.05 * poc_vol
        lvn_prices = sorted(
            bin_prices[i] for i in range(n_bins) if bin_vols[i] < lvn_threshold
        )
        # Keep only LVNs inside the value area (more meaningful)
        lvn_prices_va = [p for p in lvn_prices if val <= p <= vah]

        # ── Text-art histogram (horizontal bars, price on right) ──────────
        max_vol = bin_vols.max()
        current_close = df["Close"].iloc[-1]

        chart_lines = []
        for i in range(n_bins - 1, -1, -1):   # top → bottom
            ratio = bin_vols[i] / max_vol if max_vol > 0 else 0
            filled = int(ratio * bar_width)
            bar = "*" * filled + " " * (bar_width - filled)

            tag = ""
            if i == poc_idx:
                tag = " ← POC"
            elif bin_prices[i] >= val and bin_prices[i] <= vah:
                tag = " [VA]" if not tag else tag
            if abs(bin_prices[i] - current_close) < (bin_prices[1] - bin_prices[0]):
                tag += " ← price"

            chart_lines.append(f"  {bin_prices[i]:>8.2f} |{bar}|{tag}")

        # ── Assemble section ──────────────────────────────────────────────
        lines = [
            f"  Price range          : {df['Low'].min():.2f} – {df['High'].max():.2f}",
            f"  Bins                 : {n_bins}  (bin width ≈ "
            f"{(df['High'].max()-df['Low'].min())/n_bins:.2f})",
            f"  Total volume (period): {int(total_vol):,}",
            "",
            f"  POC  (Point of Control)  : {poc_price:.2f}  "
            f"[{poc_vol/total_vol*100:.1f}% of period vol]",
            f"  Value Area (70%)         : {val:.2f} – {vah:.2f}",
            f"  VAH  (Value Area High)   : {vah:.2f}",
            f"  VAL  (Value Area Low)    : {val:.2f}",
            f"  HVN  (High Volume Nodes) : {', '.join(f'{p:.2f}' for p in hvn_prices)}",
        ]
        if lvn_prices_va:
            lines.append(
                f"  LVN  (Low Volume Nodes, inside VA): "
                f"{', '.join(f'{p:.2f}' for p in lvn_prices_va[:5])}"
            )

        pos = ("inside Value Area" if val <= current_close <= vah
            else ("above VAH" if current_close > vah else "below VAL"))
        lines.append(f"  Current price vs VA      : {current_close:.2f}  ({pos})")

        lines.append("")
        lines.append("  Volume Profile (price ↑, bar = relative vol):")
        lines.extend(chart_lines)

        return "\n".join(lines)


    # ─────────────────────────────────────────────
    # 4.  DOW / PRICE-ACTION STRUCTURE (BOS STATE MACHINE)
    # ─────────────────────────────────────────────

    def _trend_structure_section(df: pd.DataFrame, order: int = 5) -> str:
        close = _normalize_close(df["Close"])
        peaks_idx, troughs_idx = _find_local_extrema(close, order=order)

        # Merge & sort pivot sequence: (index_position, price, type)
        pivots = ([(i, float(close.iloc[i]), "H") for i in peaks_idx] +
                [(i, float(close.iloc[i]), "L") for i in troughs_idx])
        pivots.sort(key=lambda x: x[0])

        if len(pivots) < 4:
            return "  Insufficient pivots to determine trend structure."

        # Extract highs and lows separately to track HH/HL/LH/LL
        highs = [(i, p) for i, p, t in pivots if t == "H"]
        lows  = [(i, p) for i, p, t in pivots if t == "L"]

        def label_sequence(seq):
            """Return list of labels for consecutive pivot pairs."""
            labels = []
            for k in range(1, len(seq)):
                if seq[k][1] > seq[k - 1][1]:
                    labels.append("HH" if seq is highs else "HL")
                else:
                    labels.append("LH" if seq is highs else "LL")
            return labels

        high_labels = label_sequence(highs)
        low_labels  = label_sequence(lows)

        # ── BOS state machine ──────────────────────────────────────────────
        # States: UPTREND, DOWNTREND, RANGING
        state = "RANGING"
        bos_events: list[str] = []
        if "Date" in df.columns:
            dates = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("").tolist()
        elif isinstance(df.index, pd.DatetimeIndex):
            dates = df.index.strftime("%Y-%m-%d").tolist()
        else:
            dates = df.index.astype(str).tolist()

        def _date_of(idx):
            pos = min(idx, len(dates) - 1)
            return dates[pos]

        # Scan through alternating H/L pairs
        last_hh = last_hl = last_lh = last_ll = None

        for i, p, t in pivots:
            if t == "H":
                if last_hh is not None:
                    if p > last_hh:
                        if state != "UPTREND":
                            bos_events.append(
                                f"BOS↑ ({_date_of(i)}, price={p:.2f}): "
                                "Structure broke upward → UPTREND begins")
                        state = "UPTREND"
                        last_hh = p
                    else:
                        last_lh = p
                        if state == "UPTREND":
                            pass   # still watching for LL confirmation
                else:
                    last_hh = p
            else:  # trough
                if last_ll is not None:
                    if p < last_ll:
                        if state != "DOWNTREND":
                            bos_events.append(
                                f"BOS↓ ({_date_of(i)}, price={p:.2f}): "
                                "Structure broke downward → DOWNTREND begins")
                        state = "DOWNTREND"
                        last_ll = p
                    else:
                        last_hl = p
                        if state == "DOWNTREND":
                            pass
                else:
                    last_ll = p

        # Recent pivot summary
        recent_highs = [f"{p:.2f}" for _, p in highs[-4:]]
        recent_lows  = [f"{p:.2f}" for _, p in lows[-4:]]

        lines = [
            f"  Current trend state  : {state}",
            f"  Recent swing highs   : {' → '.join(recent_highs)}",
            f"  Recent swing lows    : {' → '.join(recent_lows)}",
            f"  Last high labels     : {' '.join(high_labels[-6:])}",
            f"  Last low labels      : {' '.join(low_labels[-6:])}",
        ]
        if bos_events:
            lines.append(f"  BOS events ({len(bos_events)} total):")
            for ev in bos_events[-3:]:   # show last 3
                lines.append(f"    • {ev}")
        else:
            lines.append("  BOS events           : None in this period")

        return "\n".join(lines)


    # ─────────────────────────────────────────────
    # 4.  BASIC STATISTICS
    # ─────────────────────────────────────────────

    def _basic_stats_section(df: pd.DataFrame) -> str:
        close = df["Close"]
        volume = df["Volume"] if "Volume" in df.columns else None

        # Returns
        daily_ret = close.pct_change().dropna()
        total_ret = (close.iloc[-1] / close.iloc[0] - 1) * 100
        ann_vol = daily_ret.std() * np.sqrt(252) * 100

        # Rolling stats
        sma5  = close.rolling(5).mean().iloc[-1]
        sma20 = close.rolling(20).mean().iloc[-1]
        sma60 = close.rolling(60).mean().iloc[-1]

        # Recent 5-day average
        avg5 = close.tail(5).mean()

        # ATR-like measure (average daily range %)
        daily_range_pct = ((df["High"] - df["Low"]) / df["Close"] * 100).mean()

        # Max drawdown
        roll_max = close.cummax()
        drawdown = (close - roll_max) / roll_max * 100
        max_dd = drawdown.min()

        # Momentum: slope of last 10 closes (normalised)
        if len(close) >= 10:
            x = np.arange(10)
            y = close.tail(10).values
            slope = np.polyfit(x, y / y[0], 1)[0] * 100   # % per day
            slope_str = f"{slope:+.2f}% per day"
        else:
            slope_str = "N/A"

        lines = [
            f"  Period return        : {total_ret:+.2f}%",
            f"  Annualised volatility: {ann_vol:.2f}%",
            f"  Avg daily range (%)  : {daily_range_pct:.2f}%",
            f"  Max drawdown         : {max_dd:.2f}%",
            f"  Last close           : {close.iloc[-1]:.4f}",
            f"  5-day avg close      : {avg5:.4f}",
            f"  SMA-5  / SMA-20 / SMA-60: {sma5:.2f} / {sma20:.2f} / {sma60:.2f}",
            f"  Price vs SMA-20      : {'above' if close.iloc[-1] > sma20 else 'below'} "
            f"({(close.iloc[-1]/sma20 - 1)*100:+.2f}%)",
            f"  Recent momentum slope: {slope_str}",
        ]

        if volume is not None and volume.sum() > 0:
            avg_vol = volume.tail(20).mean()
            last_vol = volume.iloc[-1]
            lines.append(
                f"  Volume (last / 20d avg): "
                f"{int(last_vol):,} / {int(avg_vol):,} "
                f"({'above' if last_vol > avg_vol else 'below'} average)"
            )

        return "\n".join(lines)
    n = len(data)
    order = max(3, n // 20)
    
    indicator_calculations = {
        "resistance_stats": _support_resistance_section,
        "pattern_stats": _patterns_section,
        "volume_stats": _volume_profile_section,
        "structure_stats": lambda df: _trend_structure_section(df, order),
        "basic_stats": _basic_stats_section,
    }
    try:
        if indicator in indicator_calculations:
            return indicator_calculations[indicator](data)
        else:
            return "Indicator not recognised. Available indicators: " + ", ".join(indicator_calculations.keys())
    except Exception as e:
        return f"Error generating briefing for {indicator}: {str(e)}"
