import argparse,asyncio,json
from app.research.backtester import run_backtest
from app.research.config import ResearchConfig
from app.research.data_store import save_dataset
from app.research.feature_engine import generate_features
from app.research.historical_collector import fetch_recent_months
from app.research.performance_report import summarize_backtest
from app.research.research_store import save_report
from app.research.sk_system_engine import calculate_sk_features
from app.research.strategy import build_strategy_signals

async def run_demo(config:ResearchConfig)->dict:
    config.data_dir.mkdir(parents=True,exist_ok=True); config.report_dir.mkdir(parents=True,exist_ok=True); results=[]; errors=[]
    for symbol in config.symbols:
        for timeframe in config.timeframes:
            print(f'[DOWNLOAD] {symbol} {timeframe}')
            try:
                candles=await fetch_recent_months(symbol,timeframe,months=config.months,limit=config.request_limit,timeout=config.request_timeout_seconds)
                if candles.empty: raise RuntimeError('No candles returned')
                save_dataset(candles,config.data_dir,symbol,timeframe)
                features=calculate_sk_features(generate_features(candles)); signals=build_strategy_signals(features,minimum_score=config.minimum_score)
                save_dataset(signals,config.data_dir,symbol,timeframe,kind='features')
                backtest=run_backtest(signals,symbol=symbol,timeframe=timeframe,initial_balance=config.initial_balance,risk_per_trade_percent=config.risk_per_trade_percent,fee_rate=config.fee_rate,slippage_rate=config.slippage_rate)
                report=summarize_backtest(backtest); save_report(config.database_path,report); results.append(report)
                print(f"[DONE] {symbol} {timeframe}: {report['trade_count']} trades | WR {report['win_rate_percent']:.2f}% | PF {report['profit_factor']:.2f} | Exp {report['expectancy_r']:.3f}R")
            except Exception as error:
                errors.append({'symbol':symbol,'timeframe':timeframe,'error':str(error)}); print(f'[ERROR] {symbol} {timeframe}: {error}')
    ranked=sorted(results,key=lambda x:(x['expectancy_r'],x['profit_factor'],-x['maximum_drawdown_percent']),reverse=True)
    output={'status':'success' if results else 'failed','results':ranked,'best_setup':ranked[0] if ranked else None,'errors':errors}
    path=config.report_dir/'demo_report.json'; path.write_text(json.dumps(output,indent=2,default=str),encoding='utf-8'); print(f'\nReport saved: {path}')
    if ranked: print('\nBEST SETUP\n'+json.dumps(ranked[0],indent=2,default=str))
    return output

def main():
    p=argparse.ArgumentParser(); p.add_argument('--symbols',default='BTCUSDT,ETHUSDT,SOLUSDT'); p.add_argument('--timeframes',default='15m,1h'); p.add_argument('--months',type=int,default=3); p.add_argument('--minimum-score',type=float,default=70)
    a=p.parse_args(); config=ResearchConfig(symbols=tuple(x.strip().upper() for x in a.symbols.split(',') if x.strip()),timeframes=tuple(x.strip() for x in a.timeframes.split(',') if x.strip()),months=max(1,a.months),minimum_score=a.minimum_score); asyncio.run(run_demo(config))

if __name__=='__main__': main()
