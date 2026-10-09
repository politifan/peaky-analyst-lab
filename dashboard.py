"""Real browser dashboard; filters and values come from the same DataFrame."""
from analysis import ROOT,basic,sha
import pipeline
import pandas as pd
import streamlit as st
st.set_page_config(page_title='Учебный магазин | Peaky Minds',layout='wide')
st.title('Учебный магазин')
st.caption('Синтетические данные Peaky Minds. Локальная панель учебного курса.')
st.button('Перечитать файлы') # Every rerun reads files; no stale cache.
sales,events=st.tabs(['Заказы','События'])
with sales:
    try:
        df=basic();df['channel']=df.channel.fillna('Неизвестный')
        channel=st.selectbox('Канал',['Все',*sorted(df.channel.unique())])
        shown=df if channel=='Все' else df.loc[df.channel==channel]
        st.caption('paid RUB. Суммы в копейках, известный итог отдельно от неизвестных заказов.')
        a,b,c=st.columns(3)
        known=shown.net_cents.sum(min_count=1)
        a.metric('Известная чистая сумма, коп. RUB','NA' if pd.isna(known) else str(int(known)))
        b.metric('Заказы',len(shown));c.metric('Неизвестная сумма',int(shown.amount_cents.isna().sum()))
        sums=shown.groupby('channel',dropna=False).net_cents.sum(min_count=1)
        chart=sums.dropna().rename('net_cents').reset_index()
        chart['net_cents']=chart.net_cents.astype('float64')
        st.bar_chart(chart,x='channel',y='net_cents',x_label='Канал',y_label='Чистая сумма, коп. RUB')
        st.dataframe(shown,use_container_width=True,hide_index=True)
        st.download_button('CSV текущего фильтра',shown.to_csv(index=False).encode('utf-8'),'filtered-orders.csv','text/csv')
        st.caption('orders SHA256: '+sha(ROOT/'data/orders.csv'))
        st.caption('Возвраты свернуты по order_id. Отчёт неполный, если есть неизвестные суммы. Валюта USD отдельно не включена. Доступный учебный период определяется created_at исходника.')
    except Exception as e:st.error('Отчёт не рассчитан: '+str(e))
with events:
    try:
        loaded=pipeline.read_current()
        if loaded is None:st.info('Сначала выполните pipeline.py --batch data/batches/first.csv')
        else:
            m,df=loaded
            st.metric('Уникальные события',len(df));st.code('version: '+m['version']+'\nmax_loaded_at: '+str(m['max_loaded_at']))
            et=st.selectbox('Тип события',['Все','view','buy'])
            s=df if et=='Все' else df.loc[df.event_type==et]
            st.dataframe(s,use_container_width=True,hide_index=True)
            st.caption('Один CURRENT выбирает manifest и CSV одной версии. Поздняя доставка сохраняет event_at. Пустой поток не означает завершённый период.')
    except Exception as e:st.error('Публикация не прошла проверку: '+str(e))
