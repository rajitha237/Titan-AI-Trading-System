from app.research.config import ResearchConfig
from app.research.research_store import get_report

def get_historical_edge(symbol:str,timeframe:str='15m',*,config:ResearchConfig|None=None)->dict:
    config=config or ResearchConfig(); report=get_report(config.database_path,symbol.upper(),timeframe)
    if not report:return {'status':'missing','decision':'NEUTRAL','confidence_adjustment':0.0,'sample_size':0,'reason':'No historical research report exists'}
    sample=int(report.get('trade_count',0)); exp=float(report.get('expectancy_r',0)); pf=float(report.get('profit_factor',0)); dd=float(report.get('maximum_drawdown_percent',0))
    if sample<config.minimum_sample_size: decision,adj,reason='NEUTRAL',0.0,'Historical sample is below the configured minimum'
    elif exp>.15 and pf>=1.25 and dd<=20: decision,adj,reason='SUPPORT',min(8.0,exp*20),'Positive expectancy and controlled drawdown'
    elif exp<0 or pf<.9: decision,adj,reason='OPPOSE',-8.0,'Historical evidence is negative'
    else: decision,adj,reason='WATCH',0.0,'Historical evidence is mixed'
    return {'status':'ready','decision':decision,'confidence_adjustment':adj,'sample_size':sample,'reason':reason,'report':report}
