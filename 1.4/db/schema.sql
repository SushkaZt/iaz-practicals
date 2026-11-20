SET client_encoding = 'UTF8';  -- file is UTF-8; needed for psql on Windows

-- Схема бази даних ІАС реєстрації та аналізу вхідних документів.
-- Виконувати в базі military_docs. Повторний запуск безпечний: наявні дані не видаляються.

CREATE TABLE IF NOT EXISTS inbound_docs (
    id             SERIAL PRIMARY KEY,
    doc_reference  VARCHAR(255) UNIQUE NOT NULL,          -- реєстраційний номер, напр. OSINT-24-001
    received_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),   -- дата і час надходження
    source_type    VARCHAR(50),                           -- HUMINT, OSINT, SIGINT, GEOINT, TECHINT
    classification VARCHAR(50)  NOT NULL,                 -- гриф: UNCLASSIFIED, CONFIDENTIAL, SECRET
    summary        TEXT         NOT NULL,                 -- короткий зміст
    analyst_notes  TEXT,                                  -- нотатки аналітика
    priority       INTEGER      NOT NULL DEFAULT 3
                   CHECK (priority BETWEEN 1 AND 3),      -- 1 високий, 2 середній, 3 низький
    status         VARCHAR(30)  NOT NULL DEFAULT 'Зареєстровано'
                   CHECK (status IN ('Зареєстровано', 'На опрацюванні', 'Опрацьовано'))
);

CREATE INDEX IF NOT EXISTS idx_received_at ON inbound_docs (received_at);
CREATE INDEX IF NOT EXISTS idx_source_type ON inbound_docs (source_type);

COMMENT ON TABLE inbound_docs IS 'Метадані вхідних аналітичних документів.';
