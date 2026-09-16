from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Float,
    MetaData,
    Table,
    Text,
)

metadata = MetaData()

experiences = Table(
    "experiences",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("experience_id", Text, nullable=False, unique=True),
    Column("created_at", Text, nullable=False),
    Column("trade_id", Text),
    Column("symbol", Text, nullable=False),
    Column("side", Text, nullable=False),
    Column("outcome", Text, nullable=False),
    Column("net_pnl", Float, nullable=False, default=0),
    Column("strategy", Text),
    Column("market_regime", Text),
    Column("session", Text),
    Column("entry_price", Float, nullable=False, default=0),
    Column("exit_price", Float, nullable=False, default=0),
    Column("duration_seconds", Float, nullable=False, default=0),
    Column("ai_score", Float, nullable=False, default=0),
    Column("confirmation_score", Float, nullable=False, default=0),
    Column("fingerprint_json", Text, nullable=False, default="{}"),
    Column("context_json", Text, nullable=False, default="{}"),
    Column("raw_json", Text, nullable=False),
)

cycles = Table(
    "cycles",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("created_at", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("symbol", Text),
    Column("decision", Text),
    Column("execution_status", Text),
    Column("execute_requested", Boolean, nullable=False, default=False),
    Column("confidence", Float, nullable=False, default=0),
    Column("quantity", Float, nullable=False, default=0),
    Column("entry_price", Float, nullable=False, default=0),
    Column("average_fill_price", Float, nullable=False, default=0),
    Column("raw_json", Text, nullable=False),
)

trade_events = Table(
    "trade_events",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("created_at", Text, nullable=False),
    Column("cycle_id", BigInteger),
    Column("symbol", Text),
    Column("event_type", Text, nullable=False),
    Column("quantity", Float, nullable=False, default=0),
    Column("price", Float, nullable=False, default=0),
    Column("realised_pnl", Float),
    Column("payload", Text, nullable=False, default="{}"),
)

notification_history = Table(
    "notification_history",
    metadata,
    Column("notification_id", BigInteger, primary_key=True, autoincrement=True),
    Column("event_key", Text, nullable=False, unique=True),
    Column("event_type", Text, nullable=False),
    Column("severity", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("message", Text, nullable=False),
    Column("cycle_id", Text),
    Column("symbol", Text),
    Column("delivery_status", Text, nullable=False),
    Column("telegram_status", Text, nullable=False),
    Column("payload_json", Text, nullable=False),
    Column("created_at", Text, nullable=False),
)

order_recovery_state = Table(
    "order_recovery_state",
    metadata,
    Column("order_key", Text, primary_key=True),
    Column("symbol", Text, nullable=False),
    Column("order_id", Text),
    Column("client_order_id", Text),
    Column("order_type", Text, nullable=False),
    Column("side", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("reduce_only", Boolean, nullable=False, default=False),
    Column("is_algo_order", Boolean, nullable=False, default=False),
    Column("quantity", Float, nullable=False, default=0),
    Column("price", Float, nullable=False, default=0),
    Column("stop_price", Float, nullable=False, default=0),
    Column("first_seen_at", Text, nullable=False),
    Column("last_seen_at", Text, nullable=False),
    Column("disappeared_at", Text),
    Column("metadata", Text, nullable=False, default="{}"),
)

performance_snapshots = Table(
    "performance_snapshots",
    metadata,
    Column("snapshot_id", BigInteger, primary_key=True, autoincrement=True),
    Column("snapshot_key", Text, nullable=False, unique=True),
    Column("payload_json", Text, nullable=False),
    Column("created_at", Text, nullable=False),
)

service_state = Table(
    "service_state",
    metadata,
    Column("state_key", Text, primary_key=True),
    Column("state_value", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
)

service_heartbeats = Table(
    "service_heartbeats",
    metadata,
    Column("heartbeat_id", BigInteger, primary_key=True, autoincrement=True),
    Column("service_name", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("mode", Text),
    Column("cycle_id", Text),
    Column("payload", Text, nullable=False, default="{}"),
    Column("created_at", Text, nullable=False),
)

completed_trades = Table(
    "completed_trades",
    metadata,
    Column("trade_id", Text, primary_key=True),
    Column("position_key", Text),
    Column("symbol", Text, nullable=False),
    Column("side", Text, nullable=False),
    Column("entry_price", Float, nullable=False),
    Column("exit_price", Float, nullable=False),
    Column("original_quantity", Float, nullable=False),
    Column("closed_quantity", Float, nullable=False),
    Column("gross_pnl", Float, nullable=False, default=0),
    Column("fees", Float, nullable=False, default=0),
    Column("net_pnl", Float, nullable=False, default=0),
    Column("outcome", Text, nullable=False),
    Column("exit_reason", Text, nullable=False),
    Column("exit_price_source", Text, nullable=False),
    Column("opened_at", Text),
    Column("closed_at", Text, nullable=False),
    Column("duration_seconds", Float, nullable=False, default=0),
    Column("metadata", Text, nullable=False, default="{}"),
)

position_state = Table(
    "position_state",
    metadata,
    Column("position_key", Text, primary_key=True),
    Column("symbol", Text, nullable=False),
    Column("side", Text, nullable=False),
    Column("entry_price", Float, nullable=False),
    Column("original_quantity", Float, nullable=False),
    Column("current_quantity", Float, nullable=False),
    Column("mark_price", Float, nullable=False, default=0),
    Column("break_even_moved", Boolean, nullable=False, default=False),
    Column("trailing_activated", Boolean, nullable=False, default=False),
    Column("trailing_stop_price", Float, nullable=False, default=0),
    Column("completed_partial_stages", Text, nullable=False, default="[]"),
    Column("protection_verified", Boolean, nullable=False, default=False),
    Column("status", Text, nullable=False, default="OPEN"),
    Column("opened_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    Column("closed_at", Text),
    Column("metadata", Text, nullable=False, default="{}"),
)

state_events = Table(
    "state_events",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("event_time", Text, nullable=False),
    Column("symbol", Text),
    Column("event_type", Text, nullable=False),
    Column("position_key", Text),
    Column("payload", Text, nullable=False, default="{}"),
)

system_locks = Table(
    "system_locks",
    metadata,
    Column("lock_name", Text, primary_key=True),
    Column("locked", Boolean, nullable=False, default=False),
    Column("reason", Text),
    Column("locked_at", Text),
    Column("expires_at", Text),
    Column("metadata", Text, nullable=False, default="{}"),
)
