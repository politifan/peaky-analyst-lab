"""One-writer local version publication; pointer updated after all candidate checks."""
from analysis import ROOT,sha,unique_rows
from pathlib import Path
import pandas as pd
import json,hashlib,os,uuid,argparse
COLS=['event_id','user_id','event_type','event_at','loaded_at']
BUSINESS=['event_id','user_id','event_type','event_at']
def events(path):
    df=pd.read_csv(path,dtype='string')
    if list(df.columns)!=COLS:raise ValueError('Missing or reordered event columns')
    if df[COLS].isna().any().any():raise ValueError('Missing event field/key')
    if not df.event_type.isin(['view','buy']).all():raise ValueError('Unknown event type')
    for c in ['event_at','loaded_at']:
        if not df[c].str.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z').all():raise ValueError('Timestamp contract requires UTC Z with second precision')
        t=pd.to_datetime(df[c],utc=True,errors='raise')
        if t.isna().any():raise ValueError('Missing timestamp')
        df[c]=t.dt.strftime('%Y-%m-%dT%H:%M:%SZ').astype('string')
    if (pd.to_datetime(df.loaded_at,utc=True)<pd.to_datetime(df.event_at,utc=True)).any():raise ValueError('Loaded before event')
    return df
def read_current(root=ROOT,version=None):
    f=root/'outputs/CURRENT.json'
    if version is None:
        if not f.exists():return None
        pointer=json.loads(f.read_text(encoding='utf-8'))
        version=pointer['version']
    if len(version)!=16 or any(c not in '0123456789abcdef' for c in version):raise ValueError('Invalid version')
    base=root/'outputs/versions'/version
    m=json.loads((base/'manifest.json').read_text(encoding='utf-8'))
    if m['version']!=version or sha(base/'events.csv')!=m['events_sha256']:raise ValueError('Published files corrupted')
    for s in m['sources']:
        source=(root/s['path']).resolve()
        if not source.is_relative_to(root.resolve()):raise ValueError('Source path outside kit')
        if sha(source)!=s['sha256']:raise ValueError('Original batch changed')
    return m,events(base/'events.csv')
def build(batch,root=ROOT,fail=None):
    root=root.resolve();batch=Path(batch).resolve()
    if not batch.is_relative_to(root):raise ValueError('Batch must be inside this kit')
    new=events(batch);old=read_current(root)
    sources=list(old[0]['sources']) if old else []
    entry={'path':batch.relative_to(root).as_posix(),'sha256':sha(batch)}
    existing=[s for s in sources if s['path']==entry['path']]
    if existing and existing[0]!=entry:raise ValueError('Recorded batch modified; restore original and use a new immutable batch name')
    if not existing:sources.append(entry)
    sources=sorted(sources,key=lambda s:s['path'])
    frames=[old[1],new] if old else [new]
    combined=pd.concat(frames,ignore_index=True)
    # Choose earliest delivery only after business content equivalence is proved.
    reduced=combined.sort_values(['event_id','loaded_at']).drop_duplicates(BUSINESS).copy()
    if reduced.event_id.duplicated().any():raise ValueError('Conflicting immutable event_id')
    reduced=reduced.sort_values('event_id').reset_index(drop=True)
    csv=reduced.to_csv(index=False,lineterminator='\n').encode('utf-8')
    content_hash=hashlib.sha256(csv).hexdigest()
    version=hashlib.sha256(csv+json.dumps(sources,sort_keys=True).encode()).hexdigest()[:16]
    base=root/'outputs/versions'/version;base.mkdir(parents=True,exist_ok=True)
    manifest={'version':version,'rows':len(reduced),'events_sha256':content_hash,'sources':sources,'max_loaded_at':None if reduced.empty else str(reduced.loaded_at.max()),'definition':'Unique immutable event_id; UTC time, earliest equivalent delivery; one local writer'}
    (base/'events.csv').write_bytes(csv)
    (base/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    if fail=='before-pointer':raise RuntimeError('Injected failure before CURRENT: previous publication retained')
    pointer=root/'outputs/CURRENT.json';tmp=pointer.with_name('CURRENT.'+uuid.uuid4().hex+'.tmp')
    tmp.write_text(json.dumps({'version':version}),encoding='utf-8');os.replace(tmp,pointer)
    read_current(root)
    return manifest
def check(root=ROOT,version=None):
    current=read_current(root,version)
    if current is None:raise ValueError('No published events')
    m,actual=current
    # Independent reconstruction from immutable source packages, not from the output.
    from csv import DictReader
    records={}
    for s in m['sources']:
        with (root/s['path']).open(encoding='utf-8',newline='') as f:
            for row in DictReader(f):
                k=row['event_id'];v=tuple(row[c] for c in BUSINESS)
                if k in records and records[k][0]!=v:raise ValueError('Source conflict')
                delivery=min(row['loaded_at'],records[k][1]) if k in records else row['loaded_at']
                records[k]=(v,delivery)
    expected=[[*v,loaded] for k,(v,loaded) in sorted(records.items())]
    got=[list(r) for r in actual[COLS].itertuples(index=False,name=None)]
    if got!=expected or len(got)!=m['rows']:raise ValueError('Published rows do not match registered source packages')
    return {'passed':True,'version':m['version'],'rows':len(got),'sources':len(m['sources'])}
def rollback(version,root=ROOT):
    if len(version)!=16 or any(c not in '0123456789abcdef' for c in version):raise ValueError('Invalid version')
    check(root,version) # Validate the entire target before exposing its pointer.
    old=root/'outputs/CURRENT.json';previous=old.read_bytes() if old.exists() else None
    tmp=old.with_name('CURRENT.'+uuid.uuid4().hex+'.tmp');tmp.write_text(json.dumps({'version':version}),encoding='utf-8');os.replace(tmp,old)
    try:return check(root)
    except Exception:
        if previous is not None:
            tmp.write_bytes(previous);os.replace(tmp,old)
        else:old.unlink()
        raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--batch');p.add_argument('--fail',choices=['before-pointer']);p.add_argument('--rollback');a=p.parse_args()
    try:
        result=rollback(a.rollback) if a.rollback else build(a.batch,fail=a.fail)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except Exception as e:p.exit(1,str(e)+'\n')
