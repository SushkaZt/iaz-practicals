# Тема 1.3. Перше середовище для ІАЗ

## Завдання
1. Встановити Git, VS Code, Python, PostgreSQL.
2. Створити репозиторій на GitHub.
3. Виконати check.py та schema.sql.

## Результати перевірки
- Python: версія 3.11.9 (віртуальне середовище 1.3/.venv). Вивід check.py:
  ```
  ✔ Python працює!
  Квадрати: [1, 4, 9, 16, 25]
  ```
- PostgreSQL: версія 17.12. Створено базу iaz_lab, у ній за schema.sql створено таблицю test_data (CREATE TABLE). Запит `SELECT id, name FROM public.test_data;` повернув 0 рядків.
- GitHub: репозиторій https://github.com/SushkaZt/iaz-practicals (приватний). Коміт 15bbec4 «Заняття 1.3: середовище, check.py, schema.sql» надіслано в гілку main командою git push.
