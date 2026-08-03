import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
import httpx
import pandas as pd
from app.research.config import FUTURES_BASE_URL, KLINES_PATH

COLUMNS=['open_time','open','high','low','close','volume','close_time','quote_asset_volume','number_of_trades','taker_buy_base','taker_buy_quote','ignore']

class HistoricalDataError(RuntimeError):
    pass

async def fetch_klines(symbol:str, interval:str, *, start_time:datetime, end_time:datetime|None=None, limit:int=1000, timeout:float=20.0)->pd.DataFrame:
    end_time=end_time or datetime.now(timezone.utc)
    cursor=int(start_time.timestamp()*1000); end_ms=int(end_time.timestamp()*1000); rows=[]
    async with httpx.AsyncClient(timeout=timeout) as client:
        while cursor < end_ms:
            response=await client.get(f'{FUTURES_BASE_URL}{KLINES_PATH}',params={'symbol':symbol.upper(),'interval':interval,'startTime':cursor,'endTime':end_ms,'limit':max(1,min(limit,1500))})
            try: response.raise_for_status()
            except httpx.HTTPError as exc: raise HistoricalDataError(f'{symbol} {interval}: {response.status_code} {response.text[:200]}') from exc
            payload=response.json()
            if not isinstance(payload,list) or not payload: break
            rows.extend(payload)
            nxt=int(payload[-1][0])+1
            if nxt<=cursor: break
            cursor=nxt
            await asyncio.sleep(0.05)
    frame=pd.DataFrame(rows,columns=COLUMNS)
    if frame.empty:return frame
    frame=frame.drop_duplicates('open_time').sort_values('open_time')
    for col in ['open','high','low','close','volume','quote_asset_volume','number_of_trades','taker_buy_base','taker_buy_quote']:
        frame[col]=pd.to_numeric(frame[col],errors='coerce')
    frame['open_time']=pd.to_datetime(frame['open_time'],unit='ms',utc=True)
    frame['close_time']=pd.to_datetime(frame['close_time'],unit='ms',utc=True)
    frame['symbol']=symbol.upper(); frame['timeframe']=interval
    return frame.reset_index(drop=True)

async def fetch_recent_months(symbol:str,interval:str,*,months:int=6,limit:int=1000,timeout:float=20.0)->pd.DataFrame:
    now=datetime.now(timezone.utc)
    return await fetch_klines(symbol,interval,start_time=now-timedelta(days=max(1,months)*30),end_time=now,limit=limit,timeout=timeout)
