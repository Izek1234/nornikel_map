# NORNIKEL R&D Knowledge Map

> Граф знаний для горно-металлургической R&D — система управления научно-технической информацией на базе графовой БД и LLM.

## Архитектура

```
document (PDF/DOCX/PPTX/TXT/MD/CSV/HTML, ≤15MB)
    ↓ parse (PyMuPDF, python-docx, python-pptx, BeautifulSoup)
  plain text
    ↓ chunk (1500 chars, 200 overlap, max 60 chunks)
  chunks
    ↓ YandexGPT / Ollama (JSON mode, одна экстракция на чанк)
  entities + relations + experiments
    ↓ post-process (числа, единицы, синонимы RU/EN, confidence)
  нормализованные факты
    ↓ Neo4j (9 типов сущностей, 9 типов отношений)
  граф знаний
    ↓ GraphRAG: FTS → seed entities → 2-hop expansion → context → LLM answer
  ответ с цитатами и источниками
```

## Быстрый старт

### 2. Локальный запуск (Development)

**Предварительные требования:**
- Python 3.11+
- Node.js 18+ и pnpm
- Neo4j 5.x (localhost:7687) или внешний инстанс
- (опционально) Ollama для локального LLM

**Backend:**
```bash
cd backend

# Создание виртуального окружения
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac

# Установка зависимостей
pip install -e .

# Запуск
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Windows (быстрый запуск):**
```bash
run.bat
```

### 3. Конфигурация (.env)

Файл `backend/.env`:

```env
# Neo4j
NEO4J_URI='bolt://5.129.210.237:7687'
NEO4J_USERNAME='neo4j'
NEO4J_PASSWORD='bogdangandon' # наш сервер с базой данных с подгруженным яндекс диском

# LLM (yandex или ollama)
LLM_PROVIDER=yandex

# YandexGPT
YANDEX_API_KEY=your_api_key
YANDEX_FOLDER_ID=your_folder_id
YANDEX_MODEL=yandexgpt/latest

# Ollama (fallback)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# Синхронизация с Яндекс Диском
YANDEX_DISK_PUBLIC_URL=https://disk.yandex.ru/d/...
SYNC_ON_STARTUP=true

# Auth
AUTH_SECRET_KEY=your_secret_key
```

Если `NEO4J_PASSWORD` не задан, система запускается в **DEMO-режиме** на встроенных тестовых данных.

Для работы с системой надо авторизоваться(это система контроля доступа для ограничения возможностей пользователей). Для входа с полными правами зайдите под логином admin и паролем admin.

### 4. Доступ

| Сервис | URL |
|--------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |
| Neo4j Browser | http://localhost:7474 |

## API Endpoints

### Системные

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/health` | Статус API, LLM, Neo4j |
| GET | `/stats` | Статистика графа (entities, facts, docs, chunks, relations) |
| GET | `/ontology` | Типы сущностей и отношений онтологии |
| GET | `/models` | Доступные LLM модели |

### Документы

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/documents/upload` | Загрузить документ (multipart/form-data) |
| POST | `/documents/import-url` | Импорт документа по URL |
| GET | `/documents` | Список загруженных документов |
| GET | `/documents/{doc_id}/details` | Детали документа (сущности, факты) |
| GET | `/documents/{name}/content` | Текстовое содержимое документа |
| POST | `/documents/{doc_id}/pause` | Приостановить обработку |
| POST | `/documents/{doc_id}/resume` | Возобновить обработку |
| POST | `/documents/{doc_id}/cancel` | Отменить обработку |
| POST | `/documents/{doc_id}/restart` | Перезапустить обработку |

### Синхронизация с Яндекс Диском

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/sync/status` | Статус автосинхронизации |
| POST | `/sync/restart` | Перезапустить синхронизацию |
| POST | `/sync/pause` | Приостановить синхронизацию |
| POST | `/sync/resume` | Возобновить синхронизацию |
| POST | `/sync/cancel` | Отменить синхронизацию |

### Граф знаний

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/graph` | Подграф сущностей (фильтры: search, type, region, min_confidence, year_from/to) |
| GET | `/entity/{key}` | Детали сущности (факты, связи, документы) |
| GET | `/entities/suggest` | Автодополнение имён сущностей |
| GET | `/search` | Поиск фактов по запросу |
| GET | `/search/facts` | Расширенный поиск фактов (geo, confidence, value_min/max, unit) |
| GET | `/gaps` | Выявление зон риска (мало фактов / низкая достоверность) |
| GET | `/compare` | Сравнение двух сущностей (параметры a, b) |

### Эксперименты

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/experiments` | Список экспериментов с параметрами |
| GET | `/experiments/card/{exp_key}` | Карточка эксперимента |

### GraphRAG Чат

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/chat` | Запрос к GraphRAG (question, region, use_cache, messages) |
| GET | `/chat/history` | История чата |
| DELETE | `/chat/history` | Очистить историю чата |

### Версионирование и аудит

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/versions/fact/{fact_key}` | История версий факта |
| POST | `/versions/fact/{fact_key}/correct` | Экспертная корректировка факта |
| POST | `/versions/fact/{fact_key}/revert` | Откат факта к предыдущей версии |
| GET | `/versions/entity/{entity_key}` | История изменений сущности |
| POST | `/versions/entity/{entity_key}/correct` | Экспертная корректировка сущности |
| GET | `/versions/document/{doc_id}` | Версии документа |
| GET | `/audit` | Лог аудита (фильтры: target_type, author, action) |
| GET | `/audit/stats` | Статистика аудита |

### Экспорт

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/export/jsonld` | Полный граф в JSON-LD |
| GET | `/export/jsonld/entity/{key}` | Сущность в JSON-LD |
| GET | `/export/jsonld/graph` | Подграф в JSON-LD (фильтры: search, type, region, year_from/to) |

### Авторизация

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/auth/register` | Регистрация пользователя (username, password, role) |
| POST | `/auth/login` | Вход (username, password) → JWT token |
| GET | `/auth/me` | Текущий пользователь |

### Онтология

**Типы сущностей (9):** Material, Process, Equipment, Property, Experiment, Publication, Expert, Facility

**Типы отношений (9):**
| Отношение | Источник | Цель | Описание |
|-----------|----------|------|----------|
| USES_MATERIAL | Experiment, Process | Material | Использует материал |
| USES_PROCESS | Experiment | Process | Использует процесс |
| USES_EQUIPMENT | Process | Equipment | Использует оборудование |
| PERFORMED_AT | Experiment | Facility | Проводится в объекте |
| OPERATES_AT_CONDITION | Equipment, Process | Property | Работает при условиях |
| VALIDATED_BY | Experiment | Expert | Валидирован экспертом |
| DESCRIBES | Publication | Experiment | Описывает эксперимент |
| PRODUCES_OUTPUT | Experiment | Property | Производит результат |
| CONTRADICTS | Experiment, Publication | Experiment, Publication | Противоречит |

## Структура проекта

```
├── backend/
│   ├── main.py            — FastAPI app, все эндпоинты
│   ├── config.py          — Настройки из .env (pydantic-settings)
│   ├── auth.py            — JWT аутентификация, роли
│   ├── graph_db.py        — Neo4j driver, Cypher запросы
│   ├── ontology.py        — Типы сущностей/отношений, валидация
│   ├── llm_client.py      — YandexGPT / Ollama клиент
│   ├── extraction.py      — LLM compatibility wrapper
│   ├── ingestion.py       — Парсинг документов (PDF/DOCX/PPTX/HTML), chunking
│   ├── import_service.py  — Фоновый пайплайн импорта документов
│   ├── postprocess.py     — Нормализация единиц, синонимы RU/EN, confidence
│   ├── chat.py            — GraphRAG retrieval + context assembly
│   ├── cache.py           — CAG caching layer (SHA-256 dedup, 7d TTL)
│   ├── comparison.py      — Deterministic entity comparison
│   ├── versioning.py      — Версионирование фактов/сущностей, аудит-лог
│   ├── experiment_store   — Хранение экспериментов с параметрами
│   ├── url_import.py      — Импорт документов по URL
│   ├── yandex_disk_sync   — Автосинхронизация с Яндекс Диском
│   ├── jsonld_export.py   — Экспорт графа в JSON-LD
│   ├── demo_data.py       — Демо-данные для DEMO-режима
│   └── pyproject.toml     — Python зависимости
├── frontend/
│   ├── app/               — Next.js pages (layout, page, viewer)
│   ├── components/        — React компоненты:
│   │   ├── graph-tab.tsx       — Визуализация графа (d3-force) + экспорт
│   │   ├── chat-tab.tsx        — GraphRAG чат + экспорт MD/PDF
│   │   ├── documents-tab.tsx   — Управление документами
│   │   ├── dashboards-tab.tsx  — Дашборды + экспорт JSON-LD
│   │   ├── audit-tab.tsx       — Аудит-лог + экспорт JSON/CSV
│   │   └── app-header.tsx      — Навигация
│   └── lib/
│       └── api.ts         — API клиент, типы, функции экспорта
├── docker-compose.yml     — Neo4j + Backend + Frontend
├── Makefile               — make up / make logs / make frontend-dev
├── run.bat                — Быстрый запуск на Windows
└── .env                   — Конфигурация (не коммитить)
```

## Технологии

- **Backend**: Python 3.11+, FastAPI, Neo4j 5.x (Cypher), httpx
- **Frontend**: Next.js, React 19, Tailwind, shadcn/ui, d3-force
- **LLM**: YandexGPT (Yandex AI Studio) / Ollama (локальный fallback)
- **CAG**: Chunk-level SHA-256 dedup + answer cache (7d TTL)
- **NLP**: LLM-based extraction + unit normalization + RU/EN synonym mapping
- **Деплой**: Docker Compose / Vercel
