"""ІАС реєстрації та аналізу вхідних документів.

Бекенд на Flask: віддає сторінку (templates/index.html) і REST API для роботи
з таблицею inbound_docs у PostgreSQL.
"""

import os
from datetime import datetime

import psycopg2
from psycopg2 import errors
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()  # читає параметри підключення з файлу .env

app = Flask(__name__, template_folder="templates", static_folder="static")
app.json.ensure_ascii = False  # кирилиця у JSON без \uXXXX

SOURCE_TYPES = ["HUMINT", "OSINT", "SIGINT", "GEOINT", "TECHINT"]
CLASSIFICATIONS = ["UNCLASSIFIED", "CONFIDENTIAL", "SECRET"]
STATUSES = ["Зареєстровано", "На опрацюванні", "Опрацьовано"]
PRIORITIES = {1: "Високий", 2: "Середній", 3: "Низький"}

DOC_COLUMNS = (
    "id, doc_reference, received_at, source_type, classification, "
    "summary, analyst_notes, priority, status"
)


def get_db_connection():
    """Відкриває з'єднання з PostgreSQL за параметрами з .env."""
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "military_docs"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
    )


def query(sql, params=None, fetch="all", commit=False):
    """Виконує параметризований SQL-запит і закриває з'єднання.

    Дані користувача завжди передаються окремо (params), а не вклеюються
    в текст запиту: це захищає від SQL-ін'єкцій.
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            result = None
            if fetch == "all":
                result = cur.fetchall()
            elif fetch == "one":
                result = cur.fetchone()
            elif fetch == "rowcount":
                result = cur.rowcount
        if commit:
            conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def serialize(doc):
    """Перетворює дату на рядок ISO 8601, зрозумілий для JavaScript."""
    doc = dict(doc)
    if isinstance(doc.get("received_at"), datetime):
        doc["received_at"] = doc["received_at"].isoformat()
    return doc


def validate(data, partial=False):
    """Перевіряє дані з форми. Повертає (очищені_дані, помилка)."""
    if not isinstance(data, dict):
        return None, "Очікується JSON-об'єкт"

    clean = {}
    required = {
        "doc_reference": "Реєстраційний номер",
        "classification": "Гриф",
        "summary": "Короткий зміст",
    }

    if not partial:
        for field, label in required.items():
            if not str(data.get(field, "")).strip():
                return None, f"Поле «{label}» обов'язкове"

    if "doc_reference" in data:
        ref = str(data["doc_reference"]).strip()
        if not ref or len(ref) > 255:
            return None, "Реєстраційний номер: від 1 до 255 символів"
        clean["doc_reference"] = ref

    if "summary" in data:
        summary = str(data["summary"]).strip()
        if not summary:
            return None, "Зміст не може бути порожнім"
        clean["summary"] = summary

    if "classification" in data:
        if data["classification"] not in CLASSIFICATIONS:
            return None, "Невідомий гриф"
        clean["classification"] = data["classification"]

    if "source_type" in data:
        src = data["source_type"] or None
        if src is not None and src not in SOURCE_TYPES:
            return None, "Невідомий тип джерела"
        clean["source_type"] = src

    if "priority" in data:
        try:
            priority = int(data["priority"])
        except (TypeError, ValueError):
            return None, "Пріоритет має бути числом 1–3"
        if priority not in PRIORITIES:
            return None, "Пріоритет має бути числом 1–3"
        clean["priority"] = priority

    if "status" in data:
        if data["status"] not in STATUSES:
            return None, "Невідомий статус"
        clean["status"] = data["status"]

    if "analyst_notes" in data:
        notes = str(data["analyst_notes"] or "").strip()
        clean["analyst_notes"] = notes or None

    if "received_at" in data and data["received_at"]:
        try:
            clean["received_at"] = datetime.fromisoformat(str(data["received_at"]))
        except ValueError:
            return None, "Неправильний формат дати"

    return clean, None


# ---------- Сторінка ----------

@app.route("/")
def index():
    return render_template(
        "index.html",
        source_types=SOURCE_TYPES,
        classifications=CLASSIFICATIONS,
        statuses=STATUSES,
        priorities=PRIORITIES,
    )


# ---------- REST API ----------

@app.route("/api/docs", methods=["GET"])
def get_docs():
    """Перелік усіх документів, найновіші першими."""
    rows = query(f"SELECT {DOC_COLUMNS} FROM inbound_docs ORDER BY received_at DESC, id DESC;")
    return jsonify([serialize(r) for r in rows])


@app.route("/api/docs", methods=["POST"])
def add_doc():
    """Реєстрація нового документа."""
    data, error = validate(request.get_json(silent=True))
    if error:
        return jsonify({"error": error}), 400

    fields = list(data.keys())
    placeholders = ", ".join(["%s"] * len(fields))
    sql = (
        f"INSERT INTO inbound_docs ({', '.join(fields)}) "
        f"VALUES ({placeholders}) RETURNING {DOC_COLUMNS};"
    )
    try:
        row = query(sql, [data[f] for f in fields], fetch="one", commit=True)
    except errors.UniqueViolation:
        return jsonify({"error": "Документ з таким реєстраційним номером уже існує"}), 409
    return jsonify(serialize(row)), 201


@app.route("/api/docs/<int:doc_id>", methods=["PATCH"])
def update_doc(doc_id):
    """Часткове оновлення, наприклад зміна статусу опрацювання."""
    data, error = validate(request.get_json(silent=True), partial=True)
    if error:
        return jsonify({"error": error}), 400
    if not data:
        return jsonify({"error": "Немає полів для оновлення"}), 400

    # Назви стовпців беруться лише з перевіреного словника, а значення передаються параметрами.
    assignments = ", ".join(f"{f} = %s" for f in data)
    sql = f"UPDATE inbound_docs SET {assignments} WHERE id = %s RETURNING {DOC_COLUMNS};"
    try:
        row = query(sql, [*data.values(), doc_id], fetch="one", commit=True)
    except errors.UniqueViolation:
        return jsonify({"error": "Документ з таким реєстраційним номером уже існує"}), 409
    if row is None:
        return jsonify({"error": "Документ не знайдено"}), 404
    return jsonify(serialize(row))


@app.route("/api/docs/<int:doc_id>", methods=["DELETE"])
def delete_doc(doc_id):
    """Видалення документа."""
    count = query("DELETE FROM inbound_docs WHERE id = %s;", (doc_id,), fetch="rowcount", commit=True)
    if count == 0:
        return jsonify({"error": "Документ не знайдено"}), 404
    return jsonify({"message": "Документ видалено"})


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Аналітика: підсумки та розподіли, пораховані засобами SQL."""
    summary = query(
        """
        SELECT COUNT(*)                                          AS total,
               COUNT(*) FILTER (WHERE priority = 1)              AS high_priority,
               COUNT(*) FILTER (WHERE status <> 'Опрацьовано')   AS open_docs,
               COUNT(*) FILTER (WHERE priority = 1
                                AND status <> 'Опрацьовано')     AS urgent_open,
               COUNT(*) FILTER (WHERE received_at >= NOW() - INTERVAL '7 days') AS last_7_days
        FROM inbound_docs;
        """,
        fetch="one",
    )

    def group_by(column):
        rows = query(
            f"SELECT COALESCE({column}::text, 'Не вказано') AS label, COUNT(*) AS count "
            f"FROM inbound_docs GROUP BY 1 ORDER BY count DESC, label;"
        )
        return [dict(r) for r in rows]

    by_priority = [
        {"label": f"{r['label']} — {PRIORITIES.get(int(r['label']), '')}", "count": r["count"]}
        for r in query(
            "SELECT priority::text AS label, COUNT(*) AS count "
            "FROM inbound_docs GROUP BY priority ORDER BY priority;"
        )
    ]

    by_day = [
        {"label": r["day"].strftime("%d.%m"), "count": r["count"]}
        for r in query(
            """
            SELECT d::date AS day, COUNT(i.id) AS count
            FROM generate_series(CURRENT_DATE - 13, CURRENT_DATE, INTERVAL '1 day') AS d
            LEFT JOIN inbound_docs i ON i.received_at::date = d::date
            GROUP BY d ORDER BY d;
            """
        )
    ]

    return jsonify(
        {
            "summary": dict(summary),
            "by_source": group_by("source_type"),
            "by_classification": group_by("classification"),
            "by_status": group_by("status"),
            "by_priority": by_priority,
            "by_day": by_day,
        }
    )


@app.errorhandler(psycopg2.OperationalError)
def db_unavailable(e):
    app.logger.error("Помилка підключення до бази даних: %s", e)
    return jsonify({"error": "Немає з'єднання з базою даних. Перевірте .env і чи запущено PostgreSQL."}), 503


if __name__ == "__main__":
    app.run(debug=True)
