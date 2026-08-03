import json,sqlite3
from datetime import datetime,timezone
from pathlib import Path

def _connect(path:Path):
    path.parent.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(path); c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE IF NOT EXISTS research_results(symbol TEXT NOT NULL,timeframe TEXT NOT NULL,strategy_name TEXT NOT NULL,updated_at TEXT NOT NULL,trade_count INTEGER NOT NULL,win_rate_percent REAL NOT NULL,profit_factor REAL NOT NULL,expectancy_r REAL NOT NULL,maximum_drawdown_percent REAL NOT NULL,return_percent REAL NOT NULL,report_json TEXT NOT NULL,PRIMARY KEY(symbol,timeframe,strategy_name))')
    return c

def save_report(database_path:Path,report:dict,*,strategy_name:str='CONFLUENCE_SK_MVP')->None:
    with _connect(database_path) as c:
        c.execute('INSERT INTO research_results VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(symbol,timeframe,strategy_name) DO UPDATE SET updated_at=excluded.updated_at,trade_count=excluded.trade_count,win_rate_percent=excluded.win_rate_percent,profit_factor=excluded.profit_factor,expectancy_r=excluded.expectancy_r,maximum_drawdown_percent=excluded.maximum_drawdown_percent,return_percent=excluded.return_percent,report_json=excluded.report_json',(report['symbol'],report['timeframe'],strategy_name,datetime.now(timezone.utc).isoformat(),int(report['trade_count']),float(report['win_rate_percent']),float(report['profit_factor']),float(report['expectancy_r']),float(report['maximum_drawdown_percent']),float(report['return_percent']),json.dumps(report,default=str))); c.commit()

def get_report(database_path:Path,symbol:str,timeframe:str,*,strategy_name:str='CONFLUENCE_SK_MVP'):
    with _connect(database_path) as c: row=c.execute('SELECT report_json FROM research_results WHERE symbol=? AND timeframe=? AND strategy_name=?',(symbol.upper(),timeframe,strategy_name)).fetchone()
    return json.loads(row['report_json']) if row else None

def list_reports(database_path:Path):
    with _connect(database_path) as c: rows=c.execute('SELECT report_json FROM research_results ORDER BY expectancy_r DESC,profit_factor DESC').fetchall()
    return [json.loads(r['report_json']) for r in rows]
