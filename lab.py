from analysis import *
import argparse,sys,shutil,tempfile,platform
import pipeline
def sql(query,root=ROOT):
    db=sqlite3.connect(':memory:')
    db.executescript((root/'sql/schema.sql').read_text(encoding='utf-8'))
    # Read-only query surface, bounded CPU; student SQL never controls files.
    def authorize(action,arg1,arg2,db_name,trigger):
        if action in [sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_FUNCTION,sqlite3.SQLITE_RECURSIVE]:return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY
    db.set_authorizer(authorize)
    ticks=0
    def progress():
        nonlocal ticks;ticks+=1;return ticks>10000
    db.set_progress_handler(progress,1000)
    cur=db.execute(query)
    rows=cur.fetchmany(1001)
    if len(rows)>1000:raise ValueError('Result limit is 1000 rows')
    names=[x[0] for x in cur.description]
    print('\t'.join(names))
    for row in rows:print('\t'.join('NULL' if x is None else str(x) for x in row))
    db.close()
def demo_errors():
    with tempfile.TemporaryDirectory(prefix='peaky-analyst-') as d:
        root=Path(d);shutil.copytree(ROOT/'data',root/'data')
        o=root/'data/orders.csv';original=o.read_bytes()
        df=pd.read_csv(o,dtype='string')
        pd.concat([df,df.iloc[[0]]]).to_csv(o,index=False)
        dup=basic(root);print('FULL DUPLICATE:',len(dup),'paid RUB rows; unique total preserved')
        o.write_bytes(original)
        changed=df.iloc[[0]].copy();changed['currency']='USD'
        pd.concat([df,changed]).to_csv(o,index=False)
        try:basic(root);raise AssertionError('Conflict accepted')
        except ValueError as e:print('CONFLICT REJECTED:',e)
        o.write_bytes(original);df.loc[0,'amount_cents']='oops';df.to_csv(o,index=False)
        try:basic(root);raise AssertionError('Invalid number accepted')
        except ValueError as e:print('NUMBER REJECTED:',e)
        o.write_bytes(original);print('RECOVERY:',export_basic(root))
def acceptance():
    with tempfile.TemporaryDirectory(prefix='peaky-acceptance-') as d:
        root=Path(d);shutil.copytree(ROOT/'data',root/'data')
        b=export_basic(root);pr=export_basic(root,True)
        v1=pipeline.build(root/'data/batches/first.csv',root)
        repeat=pipeline.build(root/'data/batches/first.csv',root)
        assert v1==repeat,'Same batch changed state'
        pointer=(root/'outputs/CURRENT.json').read_bytes()
        try:pipeline.build(root/'data/batches/late.csv',root,fail='before-pointer');raise AssertionError('Fault injection ignored')
        except RuntimeError:pass
        assert (root/'outputs/CURRENT.json').read_bytes()==pointer,'Partial publication exposed'
        v2=pipeline.build(root/'data/batches/late.csv',root)
        assert v2['rows']==6
        try:pipeline.build(root/'data/batches/conflict.csv',root);raise AssertionError('Conflict accepted')
        except ValueError:pass
        assert pipeline.check(root)['version']==v2['version']
        pipeline.rollback(v1['version'],root);assert pipeline.check(root)['rows']==4
        pipeline.rollback(v2['version'],root);assert pipeline.check(root)['rows']==6
        er=experiment()
        assert er['difference']>0 and er['nA']==2000
        result={'passed':True,'basic':b,'project':pr,'repeat':True,'late':True,'partial_failure':True,'conflict_rejected':True,'rollback':True,'experiment':er,'platform':platform.platform(),'python':sys.version.split()[0]}
        print(json.dumps(result,ensure_ascii=False,indent=2));return result
def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('doctor');sq=sub.add_parser('sql');sq.add_argument('query')
    sf=sub.add_parser('sql-file');sf.add_argument('path')
    b=sub.add_parser('build-basic');b.add_argument('--project',action='store_true')
    c=sub.add_parser('check-basic');c.add_argument('--csv',required=True);c.add_argument('--project',action='store_true')
    sub.add_parser('demo-errors');sub.add_parser('acceptance');sub.add_parser('check-pipeline')
    a=p.parse_args()
    try:
        if a.action=='doctor':
            import scipy,streamlit
            print('Python:',sys.version.split()[0],'\npandas:',pd.__version__,'\nSciPy:',scipy.__version__,'\nStreamlit:',streamlit.__version__,'\nKit:',ROOT)
        elif a.action=='sql':sql(a.query)
        elif a.action=='sql-file':sql(Path(a.path).read_text(encoding='utf-8'))
        elif a.action=='build-basic':print(json.dumps(export_basic(project=a.project),ensure_ascii=False,indent=2))
        elif a.action=='check-basic':print(json.dumps(verify_basic(a.csv,project=a.project),ensure_ascii=False,indent=2))
        elif a.action=='demo-errors':demo_errors()
        elif a.action=='check-pipeline':print(json.dumps(pipeline.check(),ensure_ascii=False,indent=2))
        elif a.action=='acceptance':acceptance()
    except Exception as e:p.exit(1,'CHECK FAILED: '+str(e)+'\n')
if __name__=='__main__':main()
