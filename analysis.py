"""Reference computations on synthetic data; explicit contracts, no private services."""
from pathlib import Path
import csv,hashlib,json,math,sqlite3
import pandas as pd
from scipy.stats import chisquare, norm
ROOT=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def raw(name,root=ROOT):
    return pd.read_csv(root/'data'/name,dtype='string')
def unique_rows(df,key,business=None):
    business=business or list(df.columns)
    if df[key].isna().any():raise ValueError('Missing key: '+key)
    clean=df.drop_duplicates(subset=business).copy()
    if clean[key].duplicated().any():raise ValueError('Conflicting key: '+key)
    return clean
def basic(root=ROOT,project=False):
    prefix='project-' if project else ''
    o=unique_rows(raw(prefix+'orders.csv',root),'order_id')
    c=raw('customers.csv',root)
    if c.customer_id.isna().any() or c.customer_id.duplicated().any():raise ValueError('Customers must be unique and nonmissing')
    r=unique_rows(raw(prefix+'refunds.csv',root),'refund_id')
    required={'order_id','customer_id','amount_cents','currency','status','created_at'}
    if not required.issubset(o.columns):raise ValueError('Missing order columns')
    o['amount_cents']=pd.to_numeric(o.amount_cents,errors='raise').astype('Int64')
    r['amount_cents']=pd.to_numeric(r.amount_cents,errors='raise').astype('Int64')
    if r.order_id.isna().any() or r.amount_cents.isna().any() or (r.amount_cents<0).any():raise ValueError('Invalid refund')
    if not r.order_id.isin(o.order_id).all():raise ValueError('Orphan refund')
    if o.customer_id.isna().any() or not o.customer_id.isin(c.customer_id).all():raise ValueError('Missing customer')
    if o.currency.isna().any() or not o.currency.isin(['RUB','USD']).all():raise ValueError('Unsupported currency')
    if not o.status.isin(['paid','cancelled']).all():raise ValueError('Invalid status')
    if (o.amount_cents.dropna()<0).any():raise ValueError('Negative order amount')
    pd.to_datetime(o.created_at,utc=True,errors='raise')
    if o.created_at.isna().any():raise ValueError('Missing created_at')
    s=o.loc[(o.status=='paid')&(o.currency=='RUB')].copy()
    rr=r.groupby('order_id',as_index=False).agg(refunded_cents=('amount_cents','sum'))
    s=s.merge(rr,on='order_id',how='left',validate='one_to_one').merge(c,on='customer_id',how='left',validate='many_to_one')
    s['refunded_cents']=s.refunded_cents.fillna(0).astype('Int64')
    s['net_cents']=s.amount_cents-s.refunded_cents
    if (s.net_cents.dropna()<0).any():raise ValueError('Refund exceeds known order amount')
    return s[['order_id','customer_id','channel','currency','amount_cents','refunded_cents','net_cents']].sort_values('order_id').reset_index(drop=True)

def independent_basic(root=ROOT,project=False):
    # CSV + SQLite takes a separate path from pandas aggregation and merge.
    db=sqlite3.connect(':memory:')
    pref='project-' if project else ''
    for n,key,columns in [('orders','order_id',['order_id','customer_id','amount_cents','currency','status']),('refunds','refund_id',['refund_id','order_id','amount_cents']),('customers','customer_id',['customer_id','channel'])]:
        fname=pref+n+'.csv' if n!='customers' else n+'.csv'
        with (root/'data'/fname).open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
        db.execute('CREATE TABLE '+n+'('+','.join(c+(' INTEGER' if c=='amount_cents' else ' TEXT') for c in columns)+')')
        unique={}
        for r in rows:
            vals=tuple(None if r[c]=='' else int(r[c]) if c=='amount_cents' else r[c] for c in columns)
            if r[key] in unique and unique[r[key]]!=vals:raise ValueError('Conflict')
            unique[r[key]]=vals
        db.executemany('INSERT INTO '+n+' VALUES('+','.join('?' for _ in columns)+')',unique.values())
    q='''SELECT o.order_id,o.customer_id,c.channel,o.currency,o.amount_cents,COALESCE(r.refunded,0),o.amount_cents-COALESCE(r.refunded,0)
    FROM orders o LEFT JOIN (SELECT order_id,SUM(amount_cents) refunded FROM refunds GROUP BY order_id) r ON o.order_id=r.order_id
    LEFT JOIN customers c ON o.customer_id=c.customer_id WHERE o.status='paid' AND o.currency='RUB' ORDER BY o.order_id'''
    rows=db.execute(q).fetchall();db.close();return rows
def normalized(df):
    return [tuple(None if pd.isna(v) else int(v) if i>=4 else str(v) for i,v in enumerate(row)) for row in df.itertuples(index=False,name=None)]
def verify_basic(path,root=ROOT,project=False):
    expected=basic(root,project);actual=pd.read_csv(path,dtype='string')
    if list(actual.columns)!=list(expected.columns):raise ValueError('Output columns/order mismatch')
    if actual.order_id.isna().any() or actual.order_id.duplicated().any():raise ValueError('Output key invalid')
    for col in ['amount_cents','refunded_cents','net_cents']:actual[col]=pd.to_numeric(actual[col],errors='raise').astype('Int64')
    actual=actual.sort_values('order_id').reset_index(drop=True)
    if normalized(actual)!=normalized(expected):raise ValueError('Output rows differ from independent recomputation')
    if normalized(expected)!=independent_basic(root,project):raise ValueError('SQL/pandas reconciliation failed')
    return {'passed':True,'rows':len(actual),'known_net_cents':int(actual.net_cents.sum()),'unknown_orders':int(actual.amount_cents.isna().sum())}
def export_basic(root=ROOT,project=False):
    df=basic(root,project);out=root/'outputs';out.mkdir(exist_ok=True)
    pref='project' if project else 'basic'
    target=out/(pref+'-report.csv')
    df.to_csv(target,index=False,encoding='utf-8',lineterminator='\n')
    result=verify_basic(target,root,project)
    result.update({'sources':{n:sha(root/'data'/n) for n in [('project-' if project else '')+'orders.csv',('project-' if project else '')+'refunds.csv','customers.csv']},'definition':'paid RUB, known amounts reported separately from unknown; refunds by order','complete':False if result['unknown_orders'] else True})
    (out/(pref+'-manifest.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
def experiment(path=None,as_of='2026-01-10T00:00:00Z'):
    df=pd.read_csv(path or ROOT/'experiments/assignments.csv',dtype='string')
    if df.user_id.isna().any() or df.user_id.duplicated().any():raise ValueError('User assigned more than once or missing')
    if not df.variant.isin(['A','B']).all():raise ValueError('Unknown variant')
    if df.exposed.isna().any() or not df.exposed.isin(['0','1']).all():raise ValueError('Invalid exposure flag')
    assigned=pd.to_datetime(df.assigned_at,utc=True,errors='raise')
    if assigned.isna().any():raise ValueError('Missing assignment time')
    cut=pd.Timestamp(as_of)
    if cut.tzinfo is None:raise ValueError('as_of must have timezone')
    mature=assigned+pd.Timedelta(days=7)<=cut
    if not mature.all():raise ValueError('Observation window not mature')
    converted=pd.to_datetime(df.converted_at,utc=True,errors='raise')
    success=converted.notna()&(converted>=assigned)&(converted<assigned+pd.Timedelta(days=7))
    counts=[int((df.variant==v).sum()) for v in ['A','B']]
    wins=[int(success[df.variant==v].sum()) for v in ['A','B']]
    if min(counts)==0:raise ValueError('Missing experiment arm')
    pa,pb=[x/n for x,n in zip(wins,counts)];na,nb=counts
    if any(x<10 or n-x<10 for x,n in zip(wins,counts)):raise ValueError('Normal approximation conditions not met')
    d=pb-pa;se=math.sqrt(pa*(1-pa)/na+pb*(1-pb)/nb)
    pooled=sum(wins)/sum(counts);se0=math.sqrt(pooled*(1-pooled)*(1/na+1/nb))
    srm=chisquare(counts,f_exp=[sum(counts)/2]*2)
    return {'nA':na,'nB':nb,'xA':wins[0],'xB':wins[1],'pA':pa,'pB':pb,'difference':d,'ci_low':d-1.96*se,'ci_high':d+1.96*se,'p_two_sided':float(2*norm.sf(abs(d/se0))),'srm_stat':float(srm.statistic),'srm_p':float(srm.pvalue),'exposedA':int((df.loc[df.variant=='A','exposed']=='1').sum()),'exposedB':int((df.loc[df.variant=='B','exposed']=='1').sum()),'as_of':as_of,'synthetic':True,'method':'Independent binary units, approximate normal 95% CI, pooled two-sided z test; assignment ITT'}
def funnel(df,as_of,days=7):
    if not isinstance(days,int) or days<=0:raise ValueError('Window must be positive integer days')
    if df.user_id.isna().any() or df.event_at.isna().any():raise ValueError('Missing funnel user/time')
    if not df.event_type.isin(['view','buy']).all():raise ValueError('Unknown funnel event type')
    df=df.copy();df.event_at=pd.to_datetime(df.event_at,utc=True)
    cut=pd.Timestamp(as_of)
    if cut.tzinfo is None:raise ValueError('as_of must have timezone')
    df=df.loc[df.event_at<cut].copy()
    start=df.loc[df.event_type=='view'].groupby('user_id').event_at.min()
    eligible=start.loc[start+pd.Timedelta(days=days)<=cut]
    converted=[]
    for uid,t in eligible.items():
        buy=df.loc[(df.user_id==uid)&(df.event_type=='buy'),'event_at']
        if ((buy>t)&(buy<t+pd.Timedelta(days=days))).any():converted.append(uid)
    return {'eligible':len(eligible),'converted':len(converted),'rate':len(converted)/len(eligible) if len(eligible) else None,'users':sorted(converted)}
