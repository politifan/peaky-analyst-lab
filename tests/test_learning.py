from pathlib import Path
import shutil,json
import pandas as pd
import pytest
from analysis import ROOT,basic,export_basic,verify_basic,independent_basic,normalized,experiment,funnel
import pipeline

@pytest.fixture
def kit(tmp_path):
    shutil.copytree(ROOT/'data',tmp_path/'data')
    return tmp_path
def test_independent_rows_and_unknown(kit):
    df=basic(kit)
    assert normalized(df)==independent_basic(kit)
    assert len(df)==4 and df.net_cents.sum()==2400 and df.net_cents.isna().sum()==1
def test_project_changes_result(kit):
    assert basic(kit,True).net_cents.sum()==9276
    assert len(basic(kit,True))==5
def test_full_duplicate_preserved(kit):
    f=kit/'data/orders.csv';df=pd.read_csv(f,dtype='string')
    pd.concat([df,df.iloc[[0]]]).to_csv(f,index=False)
    assert normalized(basic(kit))==independent_basic(kit)
    assert basic(kit).net_cents.sum()==2400
def test_conflict_blocks_currency(kit):
    f=kit/'data/orders.csv';df=pd.read_csv(f,dtype='string');bad=df.iloc[[0]].copy();bad.currency='USD'
    pd.concat([df,bad]).to_csv(f,index=False)
    with pytest.raises(ValueError,match='Conflicting'):basic(kit)
def test_customer_duplicates_block(kit):
    f=kit/'data/customers.csv';df=pd.read_csv(f,dtype='string');pd.concat([df,df.iloc[[0]]]).to_csv(f,index=False)
    with pytest.raises(ValueError,match='unique'):basic(kit)
@pytest.mark.parametrize('bad',['oops','1.5','-1'])
def test_invalid_money(kit,bad):
    f=kit/'data/orders.csv';df=pd.read_csv(f,dtype='string');df.loc[0,'amount_cents']=bad;df.to_csv(f,index=False)
    with pytest.raises((ValueError,TypeError)):basic(kit)
def test_output_wrong_cent_rejected(kit):
    export_basic(kit);f=kit/'outputs/basic-report.csv';df=pd.read_csv(f,dtype='string');df.loc[0,'net_cents']='701';df.to_csv(f,index=False)
    with pytest.raises(ValueError,match='differ'):verify_basic(f,kit)
def test_output_missing_key_rejected(kit):
    export_basic(kit);f=kit/'outputs/basic-report.csv';df=pd.read_csv(f,dtype='string');df=df.iloc[1:];df.to_csv(f,index=False)
    with pytest.raises(ValueError,match='differ'):verify_basic(f,kit)
def test_empty_valid_orders(kit):
    for n in ['orders','refunds']:
        f=kit/'data'/f'{n}.csv';pd.read_csv(f).iloc[:0].to_csv(f,index=False)
    assert basic(kit).empty
    assert export_basic(kit)['rows']==0
def test_repeat_late_empty(kit):
    a=pipeline.build(kit/'data/batches/first.csv',kit)
    assert a==pipeline.build(kit/'data/batches/first.csv',kit)
    b=pipeline.build(kit/'data/batches/late.csv',kit)
    assert b['rows']==6 and pipeline.check(kit)['rows']==6
    c=pipeline.build(kit/'data/batches/empty.csv',kit)
    assert c['rows']==6
def test_partial_preserves_pointer_then_retry(kit):
    a=pipeline.build(kit/'data/batches/first.csv',kit);pointer=(kit/'outputs/CURRENT.json').read_bytes()
    with pytest.raises(RuntimeError,match='Injected'):pipeline.build(kit/'data/batches/late.csv',kit,'before-pointer')
    assert (kit/'outputs/CURRENT.json').read_bytes()==pointer
    assert pipeline.check(kit)['version']==a['version']
    assert pipeline.build(kit/'data/batches/late.csv',kit)['rows']==6
def test_conflict_preserves_old(kit):
    a=pipeline.build(kit/'data/batches/first.csv',kit)
    with pytest.raises(ValueError,match='Conflicting'):pipeline.build(kit/'data/batches/conflict.csv',kit)
    assert pipeline.check(kit)['version']==a['version']
def test_corrupt_output_rejected(kit):
    a=pipeline.build(kit/'data/batches/first.csv',kit)
    f=kit/'outputs/versions'/a['version']/'events.csv';f.write_text(f.read_text().replace('view','buy',1))
    with pytest.raises(ValueError,match='corrupted'):pipeline.check(kit)
def test_original_batch_modified_rejected(kit):
    pipeline.build(kit/'data/batches/first.csv',kit)
    f=kit/'data/batches/first.csv';f.write_text(f.read_text().replace('view','buy',1))
    with pytest.raises(ValueError,match='changed'):pipeline.check(kit)
def test_rollback_and_bad_target_preserve(kit):
    a=pipeline.build(kit/'data/batches/first.csv',kit);b=pipeline.build(kit/'data/batches/late.csv',kit)
    assert pipeline.rollback(a['version'],kit)['rows']==4
    pointer=(kit/'outputs/CURRENT.json').read_bytes()
    with pytest.raises((ValueError,FileNotFoundError)):pipeline.rollback('0'*16,kit)
    assert (kit/'outputs/CURRENT.json').read_bytes()==pointer
    assert pipeline.rollback(b['version'],kit)['rows']==6
def test_funnel_order_right_boundary_maturity():
    df=pd.DataFrame([
      ['A','view','2026-01-01T00:00:00Z'],['A','view','2026-01-02T00:00:00Z'],['A','buy','2026-01-03T00:00:00Z'],
      ['B','view','2026-01-01T00:00:00Z'],['B','buy','2026-01-08T00:00:00Z'],
      ['C','buy','2025-12-31T00:00:00Z'],['C','view','2026-01-01T00:00:00Z'],
      ['D','view','2026-01-09T00:00:00Z']
    ],columns=['user_id','event_type','event_at'])
    r=funnel(df,'2026-01-10T00:00:00Z');assert r['eligible']==3 and r['converted']==1 and r['users']==['A']
def test_experiment_actual_counts_ci_srm():
    r=experiment();assert (r['nA'],r['nB'],r['xA'],r['xB'])==(2000,2000,200,240)
    assert r['difference']==pytest.approx(.02) and 0<r['ci_low']<.01<r['ci_high']
    assert r['srm_stat']==0 and r['p_two_sided']>.0125
def test_assignment_duplicate_and_immature_rejected():
    with pytest.raises(ValueError,match='assigned'):experiment(ROOT/'experiments/assignments-defect.csv')
    with pytest.raises(ValueError,match='mature'):experiment(as_of='2026-01-03T00:00:00Z')
def test_streamlit_filter_same_table():
    from streamlit.testing.v1 import AppTest
    app=AppTest.from_file(str(ROOT/'dashboard.py'),default_timeout=15).run()
    assert not app.exception
    assert app.metric[0].value=='2400' and app.metric[1].value=='4'
    app.selectbox[0].select('search').run()
    assert app.metric[0].value=='2400' and app.metric[1].value=='2'
    app.selectbox[0].select('email').run()
    assert app.metric[0].value=='0' and app.metric[1].value=='1'
