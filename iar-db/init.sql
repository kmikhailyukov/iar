-- IAR Database DDL + Seed Data

CREATE TABLE assignments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    text            TEXT NOT NULL,
    author_id       VARCHAR(255) DEFAULT 'system',
    due_date        TIMESTAMPTZ,
    priority        VARCHAR(10) DEFAULT 'MEDIUM',
    status          VARCHAR(30) DEFAULT 'NEW',
    bpm_instance_id VARCHAR(255),
    -- классификация
    suggested_dept      VARCHAR(50),
    suggested_executor  VARCHAR(255),
    confidence          NUMERIC(4,3),
    confidence_zone     VARCHAR(10),
    justification       TEXT,
    top3_json           JSONB,
    -- решение руководителя
    assigned_dept       VARCHAR(50),
    assigned_to         VARCHAR(255),
    assigned_by         VARCHAR(255) DEFAULT 'manager1',
    assigned_at         TIMESTAMPTZ,
    assignment_action   VARCHAR(20),
    manager_comment     TEXT,
    -- оспаривание исполнителем
    disputed_dept       VARCHAR(50),
    -- lotus mock
    lotus_id            VARCHAR(255) UNIQUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE decision_log (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assignment_id UUID REFERENCES assignments(id),
    actor_id      VARCHAR(255),
    action        VARCHAR(30),
    payload       JSONB,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE knowledge_base_docs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_type     VARCHAR(20),
    dept_code    VARCHAR(50),
    employee_id  VARCHAR(50),
    content_json JSONB NOT NULL,
    source_file  VARCHAR(255),
    version      INTEGER DEFAULT 1,
    archived     BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Lotus mock: входящие "поручения" из Notes
CREATE TABLE lotus_assignments (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    text       TEXT NOT NULL,
    author     VARCHAR(255) DEFAULT 'Руководитель',
    due_date   TIMESTAMPTZ,
    priority   VARCHAR(10) DEFAULT 'MEDIUM',
    picked_up  BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Departments hierarchy + assignment rights
-- ============================================================
CREATE TABLE departments (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code         VARCHAR(50) UNIQUE NOT NULL,
    name         VARCHAR(255) NOT NULL,
    parent_id    UUID REFERENCES departments(id),
    functions_text TEXT,
    archived     BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE assignment_rights (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_dept_id UUID NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    to_dept_id   UUID NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(from_dept_id, to_dept_id)
);

INSERT INTO departments (code, name, functions_text) VALUES
('ДОЭ',    'Департамент операционной эффективности',
 'Реинжиниринг бизнес-процессов. Контроль KPI. Оптимизация затрат. Нормирование труда. Операционный аудит.'),
('ДУКО',   'Департамент управления клиентским опытом',
 'Обслуживание клиентов. Управление NPS. Обработка жалоб и обращений. Клиентский сервис. Удовлетворённость пользователей.'),
('ДПОТ',   'Департамент проектов и операционных трансформаций',
 'Управление проектами. Цифровая трансформация. Разработка дорожных карт. Agile/Scrum. Стратегические инициативы.'),
('УДЦТиЭ', 'Управление цифровых технологий и экосистем',
 'Цифровые технологии. IT-платформы. Автоматизация и роботизация процессов. Технологические инновации. Системная интеграция.');

INSERT INTO assignment_rights (from_dept_id, to_dept_id)
SELECT a.id, b.id FROM departments a CROSS JOIN departments b WHERE a.id <> b.id;

-- ============================================================
-- Users
-- ============================================================
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id VARCHAR(50) UNIQUE NOT NULL,
    name        VARCHAR(255) NOT NULL,
    position    VARCHAR(255),
    role        VARCHAR(20) NOT NULL DEFAULT 'EXECUTOR',
    dept_id     UUID REFERENCES departments(id),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO users (employee_id, name, position, role, dept_id) VALUES
('USR_ADMIN', 'Администратор',      'Системный администратор',                          'ADMIN',    NULL),
('MGR_GD',    'Ерлан Сейткали',     'Генеральный директор',                             'MANAGER',  NULL),
('MGR_DOE',   'Руководитель ДОЭ',   'Директор департамента', 'MANAGER', (SELECT id FROM departments WHERE code='ДОЭ')),
('MGR_DUKO',  'Руководитель ДУКО',  'Директор департамента', 'MANAGER', (SELECT id FROM departments WHERE code='ДУКО')),
('MGR_DPOT',  'Руководитель ДПОТ',  'Директор департамента', 'MANAGER', (SELECT id FROM departments WHERE code='ДПОТ')),
('MGR_UDCTIE','Руководитель УДЦТиЭ','Директор управления',   'MANAGER', (SELECT id FROM departments WHERE code='УДЦТиЭ')),
('EMP_001',   'Алексей Петров',     'Главный менеджер по операционной эффективности',   'EXECUTOR', (SELECT id FROM departments WHERE code='ДОЭ')),
('EMP_002',   'Мария Иванова',      'Менеджер по клиентскому опыту',                    'EXECUTOR', (SELECT id FROM departments WHERE code='ДУКО')),
('EMP_003',   'Дмитрий Сидоров',    'Менеджер проектов трансформации',                  'EXECUTOR', (SELECT id FROM departments WHERE code='ДПОТ')),
('EMP_004',   'Елена Козлова',      'Управляющий директор цифровых технологий',         'EXECUTOR', (SELECT id FROM departments WHERE code='УДЦТиЭ'));

-- ============================================================
-- Seed: DEPT_REGULATION docs
-- ============================================================
INSERT INTO knowledge_base_docs (doc_type, dept_code, content_json, source_file) VALUES
(
    'DEPT_REGULATION',
    'ДОЭ',
    '{"code":"ДОЭ","name":"Департамент операционной эффективности","functions":["реинжиниринг бизнес-процессов","контроль KPI","оптимизация затрат","нормирование труда","операционный аудит"]}',
    'reg_doe.pdf'
),
(
    'DEPT_REGULATION',
    'ДУКО',
    '{"code":"ДУКО","name":"Департамент управления клиентским опытом","functions":["обслуживание клиентов","управление NPS","обработка жалоб","клиентский сервис","удовлетворённость клиентов","поддержка пользователей"]}',
    'reg_duko.pdf'
),
(
    'DEPT_REGULATION',
    'ДПОТ',
    '{"code":"ДПОТ","name":"Департамент проектов и операционных трансформаций","functions":["управление проектами","цифровая трансформация","дорожные карты","agile-методологии","стратегические инициативы","инновационные программы"]}',
    'reg_dpot.pdf'
),
(
    'DEPT_REGULATION',
    'УДЦТиЭ',
    '{"code":"УДЦТиЭ","name":"Управление цифровых технологий и экосистем","functions":["цифровые технологии","IT-платформы","автоматизация процессов","технологические инновации","системная интеграция","цифровые экосистемы"]}',
    'reg_udctie.pdf'
);

-- ============================================================
-- Seed: JOB_DESC docs
-- ============================================================
INSERT INTO knowledge_base_docs (doc_type, dept_code, employee_id, content_json, source_file) VALUES
(
    'JOB_DESC',
    'ДОЭ',
    'EMP_001',
    '{"employee_id":"EMP_001","name":"Алексей Петров","position":"Главный менеджер по операционной эффективности","dept_code":"ДОЭ","responsibilities":["анализ и оптимизация бизнес-процессов","разработка KPI","снижение операционных затрат","методология реинжиниринга"]}',
    'jd_emp001.pdf'
),
(
    'JOB_DESC',
    'ДУКО',
    'EMP_002',
    '{"employee_id":"EMP_002","name":"Мария Иванова","position":"Менеджер по клиентскому опыту","dept_code":"ДУКО","responsibilities":["мониторинг NPS","работа с обращениями клиентов","улучшение клиентского сервиса","обучение сотрудников поддержки"]}',
    'jd_emp002.pdf'
),
(
    'JOB_DESC',
    'ДПОТ',
    'EMP_003',
    '{"employee_id":"EMP_003","name":"Дмитрий Сидоров","position":"Менеджер проектов трансформации","dept_code":"ДПОТ","responsibilities":["управление портфелем проектов","цифровизация процессов","составление дорожных карт","Agile/Scrum фасилитация"]}',
    'jd_emp003.pdf'
),
(
    'JOB_DESC',
    'УДЦТиЭ',
    'EMP_004',
    '{"employee_id":"EMP_004","name":"Елена Козлова","position":"Управляющий директор цифровых технологий","dept_code":"УДЦТиЭ","responsibilities":["стратегия цифровых технологий","управление IT-платформами","автоматизация и роботизация","технологические партнёрства"]}',
    'jd_emp004.pdf'
);

-- ============================================================
-- Seed: Тестовые поручения в Lotus
-- ============================================================
INSERT INTO lotus_assignments (text, author, due_date, priority, picked_up) VALUES
(
    'Провести анализ текущих бизнес-процессов в отделе закупок и подготовить предложения по оптимизации затрат и повышению операционной эффективности.',
    'Генеральный директор',
    NOW() + INTERVAL '7 days',
    'HIGH',
    FALSE
),
(
    'Разработать дорожную карту цифровой трансформации на 2025 год с учётом внедрения agile-методологий в ключевые проекты компании.',
    'Руководитель',
    NOW() + INTERVAL '14 days',
    'MEDIUM',
    FALSE
);
