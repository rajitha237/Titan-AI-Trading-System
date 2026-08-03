"""
TitanAI Iceberg Candidate Detector v2

Detects possible iceberg-style institutional liquidity by comparing
large bid and ask walls from the current order-book snapshot.

Important:
A single snapshot cannot prove a true iceberg order.
This engine detects iceberg candidates and liquidity concentration.
Repeated refill detection requires tracking multiple snapshots.
"""

ICEBERG_VALUE_THRESHOLD = 100_000.0
MIN_WALL_COUNT = 3

MIN_DOMINANCE_RATIO = 1.20
STRONG_DOMINANCE_RATIO = 1.75

MAX_RETURNED_WALLS = 10


def _extract_large_walls(
    levels: list,
    threshold: float,
) -> list:
    walls = []

    for level in levels:
        try:
            price = float(level[0])
            quantity = float(level[1])
            value = price * quantity

            if value < threshold:
                continue

            walls.append({
                "price": price,
                "qty": quantity,
                "value": round(value, 2),
            })

        except (TypeError, ValueError, IndexError):
            continue

    return walls


def _calculate_dominance_ratio(
    dominant_value: float,
    opposite_value: float,
) -> float:
    if opposite_value <= 0:
        return 999.0 if dominant_value > 0 else 1.0

    return dominant_value / opposite_value


def _calculate_strength(
    dominant_count: int,
    opposite_count: int,
    dominant_value: float,
    opposite_value: float,
) -> int:
    count_advantage = max(
        0,
        dominant_count - opposite_count,
    )

    dominance_ratio = _calculate_dominance_ratio(
        dominant_value,
        opposite_value,
    )

    strength = 45

    strength += min(
        20,
        count_advantage * 5,
    )

    if dominance_ratio >= 3.0:
        strength += 30
    elif dominance_ratio >= STRONG_DOMINANCE_RATIO:
        strength += 20
    elif dominance_ratio >= MIN_DOMINANCE_RATIO:
        strength += 10

    return max(
        0,
        min(100, int(round(strength))),
    )


def detect_iceberg(
    order_book: dict | None,
    value_threshold: float = ICEBERG_VALUE_THRESHOLD,
    minimum_wall_count: int = MIN_WALL_COUNT,
) -> dict:
    order_book = order_book or {}

    bids = order_book.get("bids", [])
    asks = order_book.get("asks", [])

    bid_walls = _extract_large_walls(
        bids,
        value_threshold,
    )

    ask_walls = _extract_large_walls(
        asks,
        value_threshold,
    )

    bid_count = len(bid_walls)
    ask_count = len(ask_walls)

    bid_total_value = sum(
        wall["value"]
        for wall in bid_walls
    )

    ask_total_value = sum(
        wall["value"]
        for wall in ask_walls
    )

    bid_average_value = (
        bid_total_value / bid_count
        if bid_count
        else 0.0
    )

    ask_average_value = (
        ask_total_value / ask_count
        if ask_count
        else 0.0
    )

    bid_dominance_ratio = _calculate_dominance_ratio(
        bid_total_value,
        ask_total_value,
    )

    ask_dominance_ratio = _calculate_dominance_ratio(
        ask_total_value,
        bid_total_value,
    )

    signal = "NEUTRAL"
    direction = "NONE"
    strength = 0
    dominant_side = "NONE"
    reasons = []

    enough_bid_walls = bid_count >= minimum_wall_count
    enough_ask_walls = ask_count >= minimum_wall_count

    bid_dominant = (
        enough_bid_walls
        and bid_total_value > ask_total_value
        and bid_dominance_ratio >= MIN_DOMINANCE_RATIO
    )

    ask_dominant = (
        enough_ask_walls
        and ask_total_value > bid_total_value
        and ask_dominance_ratio >= MIN_DOMINANCE_RATIO
    )

    if bid_dominant:
        signal = "BUY_ICEBERG"
        direction = "BULLISH"
        dominant_side = "BID"

        strength = _calculate_strength(
            dominant_count=bid_count,
            opposite_count=ask_count,
            dominant_value=bid_total_value,
            opposite_value=ask_total_value,
        )

        reasons.append(
            "Large bid-wall liquidity dominates ask-wall liquidity"
        )

        if bid_count > ask_count:
            reasons.append(
                "Bid side has more large liquidity walls"
            )

        if bid_dominance_ratio >= STRONG_DOMINANCE_RATIO:
            reasons.append(
                "Bid liquidity value shows strong dominance"
            )

    elif ask_dominant:
        signal = "SELL_ICEBERG"
        direction = "BEARISH"
        dominant_side = "ASK"

        strength = _calculate_strength(
            dominant_count=ask_count,
            opposite_count=bid_count,
            dominant_value=ask_total_value,
            opposite_value=bid_total_value,
        )

        reasons.append(
            "Large ask-wall liquidity dominates bid-wall liquidity"
        )

        if ask_count > bid_count:
            reasons.append(
                "Ask side has more large liquidity walls"
            )

        if ask_dominance_ratio >= STRONG_DOMINANCE_RATIO:
            reasons.append(
                "Ask liquidity value shows strong dominance"
            )

    elif enough_bid_walls and enough_ask_walls:
        signal = "BALANCED_ICEBERG_ACTIVITY"
        direction = "NONE"
        dominant_side = "BALANCED"

        strength = min(
            60,
            30 + min(bid_count, ask_count) * 3,
        )

        reasons.append(
            "Large institutional-style liquidity exists on both sides"
        )
        reasons.append(
            "Neither bid nor ask liquidity has sufficient dominance"
        )

    elif enough_bid_walls:
        signal = "BUY_ICEBERG"
        direction = "BULLISH"
        dominant_side = "BID"

        strength = _calculate_strength(
            dominant_count=bid_count,
            opposite_count=ask_count,
            dominant_value=bid_total_value,
            opposite_value=ask_total_value,
        )

        reasons.append(
            "Multiple large bid walls detected with limited ask opposition"
        )

    elif enough_ask_walls:
        signal = "SELL_ICEBERG"
        direction = "BEARISH"
        dominant_side = "ASK"

        strength = _calculate_strength(
            dominant_count=ask_count,
            opposite_count=bid_count,
            dominant_value=ask_total_value,
            opposite_value=bid_total_value,
        )

        reasons.append(
            "Multiple large ask walls detected with limited bid opposition"
        )

    else:
        reasons.append(
            "No dominant iceberg-style liquidity concentration detected"
        )

    return {
        "status": "ready",
        "signal": signal,
        "direction": direction,
        "strength": strength,
        "dominant_side": dominant_side,
        "value_threshold": value_threshold,
        "minimum_wall_count": minimum_wall_count,
        "bid_icebergs": bid_walls[:MAX_RETURNED_WALLS],
        "ask_icebergs": ask_walls[:MAX_RETURNED_WALLS],
        "bid_count": bid_count,
        "ask_count": ask_count,
        "bid_total_value": round(
            bid_total_value,
            2,
        ),
        "ask_total_value": round(
            ask_total_value,
            2,
        ),
        "bid_average_value": round(
            bid_average_value,
            2,
        ),
        "ask_average_value": round(
            ask_average_value,
            2,
        ),
        "bid_dominance_ratio": round(
            bid_dominance_ratio,
            4,
        ),
        "ask_dominance_ratio": round(
            ask_dominance_ratio,
            4,
        ),
        "candidate_only": True,
        "reasons": reasons,
    }