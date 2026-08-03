"""
TitanAI Pattern Similarity Engine v1

Finds previous market memories similar to the current setup.
"""

from app.memory.memory_engine import get_memory_records


def setup_similarity(current: dict, past: dict) -> int:
    score = 0

    if current.get("symbol") == past.get("symbol"):
        score += 20

    if current.get("order_book_pressure") == past.get("order_book_pressure"):
        score += 15

    if current.get("order_flow_pressure") == past.get("order_flow_pressure"):
        score += 20

    if current.get("technical_trend") == past.get("technical_trend"):
        score += 15

    if current.get("macd_direction") == past.get("macd_direction"):
        score += 10

    if current.get("multi_timeframe_trend") == past.get("multi_timeframe_trend"):
        score += 15

    current_quality = current.get("quality_score") or 0
    past_quality = past.get("quality_score") or 0

    if abs(current_quality - past_quality) <= 10:
        score += 5

    return min(score, 100)


def find_similar_setups(
    current_setup: dict,
    min_similarity: int = 70,
) -> dict:
    memories = get_memory_records()
    matches = []

    for memory in memories:
        similarity = setup_similarity(current_setup, memory)

        if similarity >= min_similarity:
            matches.append({
                "similarity": similarity,
                "memory": memory,
            })

    wins = 0
    losses = 0

    for match in matches:
        result = match["memory"].get("result")

        if result == "WIN":
            wins += 1
        elif result == "LOSS":
            losses += 1

    closed = wins + losses
    win_rate = (wins / closed * 100) if closed else None

    return {
        "status": "success",
        "total_memories": len(memories),
        "matches": len(matches),
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "top_matches": sorted(
            matches,
            key=lambda x: x["similarity"],
            reverse=True,
        )[:10],
    }