-- MAX Study: scheduled tests + subject
-- Выполнить в Railway Postgres (Query / psql)

-- Предмет у тестов
ALTER TABLE tests ADD COLUMN IF NOT EXISTS subject VARCHAR(100);

-- Анонсы предстоящих тестов
CREATE TABLE IF NOT EXISTS scheduled_tests (
    id                  SERIAL PRIMARY KEY,
    teacher_id          INTEGER NOT NULL REFERENCES users(id),
    class_id            INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    title               VARCHAR(255) NOT NULL,
    subject             VARCHAR(100) NOT NULL,
    description         TEXT,
    scheduled_date      TIMESTAMP NOT NULL,
    materials_text      TEXT,
    notified_day_before BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_scheduled_tests_teacher ON scheduled_tests(teacher_id);
CREATE INDEX IF NOT EXISTS ix_scheduled_tests_class ON scheduled_tests(class_id);
CREATE INDEX IF NOT EXISTS ix_scheduled_tests_date ON scheduled_tests(scheduled_date);

-- (Опционально) удалить пустые классы учителей, у кого больше одного класса
-- DELETE FROM classes c
-- WHERE NOT EXISTS (SELECT 1 FROM class_members m WHERE m.class_id = c.id);
