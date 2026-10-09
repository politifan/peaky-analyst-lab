# Аналитик данных — учебный магазин Peaky Minds
Базовый: https://stepik.org/course/301879
Продвинутый: https://stepik.org/course/301880

Начало: скачайте ZIP релиза course-v3.0.0, распакуйте; first-report.xlsx открывается в Calc/Excel без Python. order_id — текст. Жёлтые ячейки — входы. Пример — одна строка на заказ. Количество и цена обязательны, пропуск даёт #N/A вместо ложного нуля. Комиссия учебная, не прибыль.

## Windows PowerShell
Установите Python 3.11 64-bit. Откройте терминал в распакованной папке.
```
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe lab.py doctor
.\.venv\Scripts\python.exe -m jupyter lab
```
Если py не найден, установите Python 3.11 с python.org и заново откройте терминал. Для FileNotFoundError сначала проверьте папку. Активировать окружение PowerShell и изменять ExecutionPolicy не требуется.

## macOS/Linux
После установки Python 3.11:
```
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python lab.py doctor
.venv/bin/python -m jupyter lab
```
Дальше python в командах ниже означает Python созданного окружения. Рекомендуется 8 ГБ RAM, 3 ГБ свободного места и интернет на установке; наборы небольшие. Авторский прогон подтверждён на Windows Python 3.11; другие ОС получают тот же код, но их установка отдельно не заявляется проверенной.

## Проверки и панель
```
python lab.py sql "SELECT order_id,status FROM orders"
python lab.py sql-file sql/customer-payments.sql
python lab.py build-basic
python lab.py check-basic --csv outputs/basic-report.csv
python lab.py build-basic --project
python lab.py check-basic --project --csv outputs/project-report.csv
python lab.py demo-errors
python pipeline.py --batch data/batches/first.csv
python pipeline.py --batch data/batches/late.csv
python lab.py check-pipeline
python -m streamlit run dashboard.py
python -m pytest -q
python lab.py acceptance
```
Streamlit открывается локально обычно http://localhost:8501. Кнопка «Перечитать файлы» обновляет входы. Не публикуйте Jupyter/Streamlit с личными данными в интернет. Порт занят — остановите свой прежний запуск Ctrl+C или добавьте --server.port 8502.

## Порядок блокнотов
01-python → 02-pandas → 03-statistics → 04-advanced → 05-experiment. В Jupyter: Kernel → Restart Kernel and Run All Cells. Проверочный блокнот показывает разобранный пример; для итогового проекта создайте my-report на project-наборе.

## Данные и диалекты
CSV синтетические, CC0. Денежные поля — целые минимальные единицы своей валюты. orders — order_id, refunds — refund_id, events — event_id, prices — исторические интервалы [from,to). Разные валюты не складываются. Неизвестная сумма сохраняется; в денежном отчёте отдельно quality=unknown. Полные повторы исключаются после сравнения бизнес-полей, конфликт ключа блокирует выпуск.

SQL Challenge Stepik использует MySQL 8; локальный помощник SQLite. Общий SELECT/WHERE/JOIN/CTE/оконный поднабор проверяется в обеих средах; для вещественного деления используйте 1.0. Времена в SQL примерах — одинаковые UTC ISO строки, для рабочих timestamp используйте диалект своей СУБД. Не запускайте sqlite-функции julianday на MySQL или MySQL DATE_ADD на SQLite.

## Сбой и возврат
Витрина pipeline — один локальный писатель. Файлы версии записываются до атомарной замены CURRENT. --fail before-pointer воспроизводит отказ; повтор того же batch завершает публикацию. Для возврата: python pipeline.py --rollback VERSION (возьмите сохранённую version из CURRENT); проверяются файлы и исходники. Сохранённые версии не удаляются автоматически. Конкурентные писатели и сеть вне контракта.

Stepik независимо выполняет конкретные SQL/Python задачи. CSV-проекты, панель и письменные выводы проходят локальную сверку и рубрику; External Grader, серверный экзамен вашего стенда и постоянная персональная проверка не подключены. Проверка локального отчёта не доказывает корректность произвольных производственных данных.
