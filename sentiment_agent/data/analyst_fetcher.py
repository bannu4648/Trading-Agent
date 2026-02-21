"""
Pulls analyst recommendations from Finnhub.

Finnhub's free tier gives 60 calls/min which is way more reliable
than yfinance's unofficial scraping. Requires a FINNHUB_API_KEY
(get one for free at https://finnhub.io/register).

Free tier only includes recommendation_trends. Price targets and
upgrade/downgrade data require a paid plan -- we try those but
gracefully fall back if they return 403.
"""
import logging
import finnhub
from sentiment_agent.config.settings import settings

logger = logging.getLogger(__name__)

# lazy-init so tests don't blow up without a key
_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = settings.finnhub_api_key
        if not api_key:
            raise ValueError(
                "FINNHUB_API_KEY is required. "
                "Get a free key at https://finnhub.io/register"
            )
        _client = finnhub.Client(api_key=api_key)
    return _client


def fetch_analyst_data(ticker: str) -> dict:
    """
    Get analyst consensus and (optionally) price targets + upgrade/downgrade actions.
    The recommendation_trends endpoint is free; others may need a paid plan.
    """
    ticker = ticker.upper()

    try:
        client = _get_client()

        # 1) recommendation trends (FREE tier) -- returns monthly snapshots
        #    each has: buy, hold, sell, strongBuy, strongSell, period
        recs = client.recommendation_trends(ticker)
        latest_rec = recs[0] if recs else {}

        strong_buy  = latest_rec.get("strongBuy", 0)
        buy_count   = latest_rec.get("buy", 0)
        hold_count  = latest_rec.get("hold", 0)
        sell_count   = latest_rec.get("sell", 0)
        strong_sell = latest_rec.get("strongSell", 0)
        total_buy   = strong_buy + buy_count
        total_sell  = strong_sell + sell_count
        analyst_count = total_buy + hold_count + total_sell

        # figure out the consensus from the counts
        if analyst_count == 0:
            recommendation_key = "none"
        elif total_buy > hold_count + total_sell:
            recommendation_key = "strong_buy" if total_buy > 2 * (hold_count + total_sell) else "buy"
        elif total_sell > hold_count + total_buy:
            recommendation_key = "strong_sell" if total_sell > 2 * (hold_count + total_buy) else "sell"
        else:
            recommendation_key = "hold"

        # 2) price targets (may need paid plan, gracefully skip if 403)
        target_mean = None
        target_high = None
        target_low  = None
        try:
            targets = client.price_target(ticker)
            target_mean = targets.get("targetMean")
            target_high = targets.get("targetHigh")
            target_low  = targets.get("targetLow")
        except Exception as e:
            if "403" in str(e):
                logger.debug(f"Price target endpoint requires paid plan, skipping")
            else:
                logger.warning(f"Could not fetch price targets for {ticker}: {e}")

        # 3) recent upgrades/downgrades (may need paid plan, gracefully skip if 403)
        recent_actions = []
        try:
            upgrades = client.upgrade_downgrade(symbol=ticker)
            for item in (upgrades or [])[:10]:
                recent_actions.append({
                    "firm":       item.get("company", ""),
                    "to_grade":   item.get("toGrade", ""),
                    "from_grade": item.get("fromGrade", ""),
                    "action":     item.get("action", ""),
                })
        except Exception as e:
            if "403" in str(e):
                logger.debug(f"Upgrade/downgrade endpoint requires paid plan, skipping")
            else:
                logger.warning(f"Could not fetch upgrades/downgrades for {ticker}: {e}")

        return {
            "ticker": ticker,
            "recommendation_key": recommendation_key,
            "analyst_count": analyst_count,
            "strong_buy": strong_buy,
            "buy": buy_count,
            "hold": hold_count,
            "sell": sell_count,
            "strong_sell": strong_sell,
            "target_mean_price": target_mean,
            "target_high_price": target_high,
            "target_low_price":  target_low,
            "current_price":     None,
            "recent_actions":    recent_actions,
        }
    except Exception as e:
        logger.error(f"Finnhub analyst data fetch error for {ticker}: {e}")
        return {
            "ticker": ticker,
            "recommendation_key": "none",
            "analyst_count": 0,
            "strong_buy": 0,
            "buy": 0,
            "hold": 0,
            "sell": 0,
            "strong_sell": 0,
            "target_mean_price": None,
            "target_high_price": None,
            "target_low_price":  None,
            "current_price":     None,
            "recent_actions":    [],
        }
