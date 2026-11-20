# Тема 1.4. ІАС обліку та аналізу вхідних документів

Навчальна інформаційно-аналітична система для реєстрації та аналізу вхідних документів.
Побудована за матеріалами заняття (`Theme 1/1.4_1.5` репозиторію викладача).
Усі дані в системі вигадані.

## Можливості

- **Реєстрація** документа: номер, дата надходження, джерело, гриф, пріоритет, зміст, нотатки аналітика.
- **Реєстр** з пошуком за будь-яким полем, фільтрами за джерелом і статусом та сортуванням кліком по заголовку.
- **Зміна статусу** опрацювання (Зареєстровано → На опрацюванні → Опрацьовано) і **видалення** документа.
- **Аналітика**: загальна кількість, надходження за 7 днів, неопрацьовані та термінові документи;
  розподіл за джерелами, грифом, пріоритетом, статусом і динаміка надходжень за 14 днів.
  Усі показники рахує PostgreSQL (`GROUP BY`, `COUNT ... FILTER`).

## Архітектура

```
Браузер (templates + static)  ⇄  Flask REST API (app.py)  ⇄  PostgreSQL (military_docs)
```

```
1.4/
├── app.py               # Flask: сторінка + REST API + аналітика
├── requirements.txt     # Flask, psycopg2-binary, python-dotenv
├── .env.example         # шаблон параметрів підключення
├── db/
│   ├── schema.sql       # таблиця inbound_docs та індекси
│   └── sample_data.sql  # 15 навчальних записів
├── templates/
│   └── index.html       # HTML-сторінка (шаблон Jinja2)
└── static/
    ├── style.css        # оформлення
    └── app.js           # логіка інтерфейсу, запити до API, діаграми
```

## База даних

Таблиця `inbound_docs`:

| Поле | Тип | Призначення |
|---|---|---|
| id | SERIAL PK | ідентифікатор |
| doc_reference | VARCHAR(255) UNIQUE NOT NULL | реєстраційний номер |
| received_at | TIMESTAMPTZ NOT NULL | дата і час надходження |
| source_type | VARCHAR(50) | HUMINT, OSINT, SIGINT, GEOINT, TECHINT |
| classification | VARCHAR(50) NOT NULL | UNCLASSIFIED, CONFIDENTIAL, SECRET |
| summary | TEXT NOT NULL | короткий зміст |
| analyst_notes | TEXT | нотатки аналітика |
| priority | INTEGER 1–3 | 1 високий, 2 середній, 3 низький |
| status | VARCHAR(30) | Зареєстровано / На опрацюванні / Опрацьовано |

## REST API

| Метод | Адреса | Дія |
|---|---|---|
| GET | `/api/docs` | перелік документів |
| POST | `/api/docs` | реєстрація документа (JSON) |
| PATCH | `/api/docs/<id>` | зміна полів, напр. `{"status": "Опрацьовано"}` |
| DELETE | `/api/docs/<id>` | видалення документа |
| GET | `/api/stats` | аналітичні показники |

Сервер перевіряє вхідні дані, використовує лише параметризовані SQL-запити (захист від SQL-ін'єкцій),
а інтерфейс екранує текст перед виведенням (захист від XSS).

## Запуск у Windows

Команди виконуються в терміналі VS Code з папки `1.4`.

1. Створити базу та таблицю (запитає пароль `postgres`):
   ```powershell
   psql -h localhost -U postgres -d postgres -c "CREATE DATABASE military_docs;"
   psql -h localhost -U postgres -d military_docs -f db/schema.sql
   psql -h localhost -U postgres -d military_docs -f db/sample_data.sql
   ```
2. Створити середовище та встановити залежності:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
3. Скопіювати `.env.example` у `.env` і вписати свій пароль PostgreSQL:
   ```powershell
   Copy-Item .env.example .env
   ```
4. Запустити сервер і відкрити http://127.0.0.1:5000:
   ```powershell
   .\.venv\Scripts\python.exe app.py
   ```

Файл `.env` з паролем не додається до Git.
