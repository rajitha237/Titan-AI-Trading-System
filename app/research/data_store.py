from pathlib import Path
import pandas as pd

def dataset_path(data_dir:Path,symbol:str,timeframe:str,*,kind:str='candles')->Path:
    return Path(data_dir)/kind/symbol.upper()/f'{timeframe}.csv'

def save_dataset(frame:pd.DataFrame,data_dir:Path,symbol:str,timeframe:str,*,kind:str='candles')->Path:
    path=dataset_path(data_dir,symbol,timeframe,kind=kind); path.parent.mkdir(parents=True,exist_ok=True); frame.to_csv(path,index=False); return path

def load_dataset(data_dir:Path,symbol:str,timeframe:str,*,kind:str='candles')->pd.DataFrame:
    path=dataset_path(data_dir,symbol,timeframe,kind=kind)
    frame=pd.read_csv(path)
    for col in ('open_time','close_time'):
        if col in frame: frame[col]=pd.to_datetime(frame[col],utc=True,errors='coerce')
    return frame
