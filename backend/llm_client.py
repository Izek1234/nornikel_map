"""Multi-provider LLM client: YandexGPT (Yandex AI Studio) or Ollama.
Controlled by LLM_PROVIDER env var."""
import json
import random
import threading
import time

import httpx

from config import settings
import logging

logger = logging.getLogger(__name__)

# ── Config from env ─────────────────────────────────────────────
PROVIDER = settings.llm_provider

# Yandex GPT
YANDEX_API_KEY = settings.yandex_api_key
YANDEX_FOLDER_ID = settings.yandex_folder_id
YANDEX_MODEL = settings.yandex_model
YANDEX_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
YANDEX_MAX_CONCURRENT = settings.yandex_max_concurrent
YANDEX_RPS_LIMIT = settings.yandex_rps_limit
YANDEX_HOURLY_LIMIT = settings.yandex_hourly_limit
YANDEX_MAX_RETRIES = settings.yandex_max_retries

_yandex_semaphore = threading.BoundedSemaphore(YANDEX_MAX_CONCURRENT)
_rate_lock = threading.Lock()
_request_timestamps: list[float] = []

# Ollama fallback
OLLAMA_BASE = settings.ollama_base_url
OLLAMA_MODEL = settings.ollama_model

# ── Prompts (materials science) ─────────────────────────────────

EXTRACTION_SYSTEM = """Ты — система извлечения знаний из научно-технических документов горно-металлургической отрасли.

СТРОГИЕ ПРАВИЛА ОНТОЛОГИИ:

Типы узлов (ТОЛЬКО эти, никаких других):
- Material: вещества, материалы, сырьё (никель, медь, гипс, штейн, шлак, электролит)
- Process: процессы, методы, технологии (выщелачивание, электроэкстракция, флотация)
- Equipment: оборудование, установки, приборы (ванна, печь, ячейка)
- Property: свойства, характеристики, числовые параметры (концентрация, температура, pH)
- Experiment: эксперименты, опыты, испытания (протокол, тест, измерение)
- Publication: публикации, статьи, патенты, отчёты
- Expert: исследователи, авторы, эксперты
- Facility: лаборатории, фабрики, рудники, объекты

Типы отношений (ТОЛЬКО эти):
- Experiment-USES_MATERIAL→Material
- Experiment-USES_PROCESS→Process
- Process-USES_MATERIAL→Material
- Process-USES_EQUIPMENT→Equipment
- Experiment-PERFORMED_AT→Facility
- Equipment-OPERATES_AT_CONDITION→Property (оборудование работает при определённых условиях: температура, давление, скорость потока)
- Process-OPERATES_AT_CONDITION→Property (процесс протекает при определённых условиях)
- Experiment-VALIDATED_BY→Expert
- Publication-DESCRIBES→Experiment
- Experiment-PRODUCES_OUTPUT→Property
- Publication-CONTRADICTS→Publication
- Experiment-CONTRADICTS→Experiment

ТЕХНОЛОГИЧЕСКИЕ ДОМЕНЫ — определи к какому(-им) доменам относится каждая сущность:
- hydrometallurgy: выщелачивание, электроэкстракция, флотация, обессоливание, водоподготовка
- pyrometallurgy: плавка, конвертирование, обжиг, печи, ПВП
- ecology: очистка газов, выбросы, водоочистка, ПДК, экология
- waste_processing: хвосты, шлаки, шлам, вторичное сырьё, переработка отходов
- mining: добыча, руда, бурение, карьер, шахта
- materials_science: свойства сплавов, коррозия, механические характеристики, термообработка
- analytics: анализ, спектрометрия, рентген, химический контроль
- economics: себестоимость, инвестиции, ТЭО, бюджет

ВАЖНО:
1. Синонимы и термины на разных языках: Обязательно сопоставляй английские и российские термины! Для каждой сущности добавляй массив "aliases" (например, русский термин, английский перевод, аббревиатура).
2. Числовые ограничения, диапазоны и свойства: Свойства экспериментов (temperature, pressure, time, atmosphere, cooling_rate, heating_rate, gas, sample_mass, ph, voltage, current_density, flow_rate, concentration) сохраняй в массиве produces_output!
3. Для каждого элемента produces_output нужно заполнить поля "value_min", "value_max", "unit" (единицы измерения), "geography" (география), "time" (год или дата) если они есть.
4. Для каждого Experiment обязательно укажи source: document_id, chunk_id, original_text.
5. Противоречия: Если в тексте явно упоминается противоречие с другими источниками (разные цифры, разные мнения), обязательно фиксируй это через отношение CONTRADICTS между Publication или Experiment, и сохраняй обе конфликтующие версии фактов!
6. Домены: Для КАЖДОЙ сущности обязательное поле "domains" — список из ["hydrometallurgy", "pyrometallurgy", "ecology", "waste_processing", "mining", "materials_science", "analytics", "economics"]. Если домен определить невозможно — ставь пустой список [].
7. География: В поле "geography" пиши ТОЛЬКО "RU" (для российских исследований) или "world" (для зарубежных/международных). Определяй по контексту: упоминание российских институтов, предприятий, авторов → "RU"; иностранные источники, международные журналы → "world".

Верни JSON строго в формате:
{
  "entities": [{"name": "...", "type": "Material|Process|...", "description": "...", "aliases": ["...", "..."], "domains": ["hydrometallurgy"]}],
  "relations": [{"source": "...", "target": "...", "type": "USES_MATERIAL|..."}],
  "experiments": [{
    "name": "...",
    "source": {"document_id": "...", "chunk_id": "...", "original_text": "..."},
    "uses_materials": ["...", "..."],
    "uses_processes": ["..."],
    "performed_at": "...",
    "produces_output": [{
      "property": "temperature",
      "value_min": 950.0,
      "value_max": 1000.0,
      "unit": "°C",
      "geography": "Russia",
      "time": "2023"
    }]
  }]
}

Не выдумывай. Только то что есть в тексте."""


REGION_SYSTEM = """Ты — классификатор географической принадлежности научно-технических данных.

Определи регион по тексту. Верни ТОЛЬКО JSON:
{"region": "RU"} — если это российское исследование (российские авторы, институты, предприятия, Норникель, Гинцветмет, МГТУ, СПбГУ, патенты РФ, ГОСТы, ПДК РФ)
{"region": "world"} — если зарубежное или международное (иностранные авторы, международные журналы, European Journal, Minerals Engineering, Hydrometallurgy, патенты US/EP/WO)

Правила:
- Норникель, Норильск, Таймыр, Кольская ГМК, Полярный филиал → RU
- Упоминание российских стандартов (ГОСТ, СанПиН, ПДК) → RU
- English-only текст без упоминания российских организаций → world
- Смешанный текст — определяй по основному источнику
- Если невозможно определить — {"region": "unknown"}"""

# CHAT_SYSTEM = """Ты — ассистент карты знаний R&D Норникель.
# Отвечай на русском, используй ТОЛЬКО предоставленный контекст.
# Указывай числа с единицами измерения.
# Если данных нет — скажи честно."""


CHAT_SYSTEM = """Ты — ассистент карты знаний R&D Норникель.
Отвечай на русском языке, используя ТОЛЬКО предоставленный контекст графа знаний (сущности, факты, фрагменты).

В твои задачи входит:
1. Точные ответы: Всегда указывай числа с единицами измерения, а также диапазоны (от value_min до value_max), если они есть.
2. Противоречия в данных: Если в контексте присутствуют факты или параметры, которые противоречат друг другу (помечены тегом [ПРОТИВОРЕЧИЕ! ВАЖНО УЧЕСТЬ], имеют разные значения для одного процесса, или связаны отношением CONTRADICTS), ты ОБЯЗАН акцентировать на этом внимание. Приведи обе версии, укажи источники и объясни возможную причину расхождения.
3. Сопоставление терминов: Учитывай, что объекты могут иметь синонимы на английском и русском языках. Если пользователь спрашивает на английском, а данные на русском (или наоборот), проводи прозрачное сопоставление терминов.
4. Контекст: Учитывай поля geography (география) и time (время), если они есть в фактах.
5. Пропущенные параметры: Если в цепочке «материал → процесс → оборудование → результат» отсутствует какой-либо элемент (нет данных о параметрах, нет связи между сущностями, неполная технологическая цепочка), ясно укажи что именно отсутствует. Формулируй: «⚠️ Отсутствует: [название параметра/звена]».
6. Противоречивые результаты тестов: Если для одной и той же комбинации «материал + режим + условие» есть разные результаты (разная температура, разный выход, разные выводы в разных источниках), обязательно выдели это секцией «⚡ Противоречия в результатах» с указанием обоих значений и источников.
7. Зоны неопределённости: Если ответ основана на малом количестве источников (1-2 факта) или на фактах с низкой достоверностью (confidence < 0.6), предупреди: «ℹ️ Основано на ограниченных данных».

Если данных нет — скажи честно, не выдумывай."""



class LLMError(Exception):
    pass


# ── Yandex GPT call ────────────────────────────────────────────

def _wait_for_yandex_budget():
    """Keep requests under Yandex per-second and hourly API quotas."""
    while True:
        now = time.monotonic()
        with _rate_lock:
            recent_window = now - 1.0
            hour_window = now - 3600.0
            _request_timestamps[:] = [ts for ts in _request_timestamps if ts >= hour_window]
            recent = [ts for ts in _request_timestamps if ts >= recent_window]

            if len(recent) < YANDEX_RPS_LIMIT and len(_request_timestamps) < YANDEX_HOURLY_LIMIT:
                _request_timestamps.append(now)
                return

            if len(_request_timestamps) >= YANDEX_HOURLY_LIMIT:
                sleep_for = max(1.0, 3600.0 - (now - _request_timestamps[0]))
            else:
                sleep_for = max(0.05, 1.0 - (now - min(recent)))

        time.sleep(min(sleep_for, 30.0))

def _call_yandex(
    prompt: str,
    max_tokens: int = 2500,
    temperature: float = 0.1,
    system_prompt: str = EXTRACTION_SYSTEM,
    history: list[dict] | None = None,
) -> str:
    """Call YandexGPT via Yandex AI Studio API."""
    if not YANDEX_API_KEY:
        raise LLMError("YANDEX_API_KEY не задан")
    if not YANDEX_FOLDER_ID:
        raise LLMError("YANDEX_FOLDER_ID не задан")

    if history is None: history = []
    msgs = [{"role": "system", "text": system_prompt}]
    for h in history:
        r = "assistant" if h["role"] == "assistant" else "user"
        msgs.append({"role": r, "text": h["content"]})
    msgs.append({"role": "user", "text": prompt})

    payload = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/{YANDEX_MODEL}",
        "completionOptions": {
            "stream": False,
            "temperature": temperature,
            "maxTokens": max_tokens,
        },
        "messages": msgs,
    }

    headers = {
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "Content-Type": "application/json",
    }
    last_error = ""
    for attempt in range(YANDEX_MAX_RETRIES + 1):
        _wait_for_yandex_budget()
        with _yandex_semaphore:
            try:
                with httpx.Client(timeout=180) as client:
                    resp = client.post(YANDEX_URL, headers=headers, json=payload)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = str(exc)
                resp = None

        if resp is not None and resp.status_code == 200:
            break

        if resp is not None:
            last_error = f"YandexGPT API error {resp.status_code}: {resp.text[:300]}"
            retryable = resp.status_code in {408, 409, 425, 429, 500, 502, 503, 504}
            retry_after = resp.headers.get("retry-after")
        else:
            retryable = True
            retry_after = None

        if not retryable or attempt >= YANDEX_MAX_RETRIES:
            raise LLMError(last_error)

        if retry_after:
            try:
                delay = float(retry_after)
            except ValueError:
                delay = 0.0
        else:
            delay = min(30.0, (2 ** attempt) + random.uniform(0.2, 1.2))
        time.sleep(delay)

    data = resp.json()
    try:
        return data["result"]["alternatives"][0]["message"]["text"]
    except (KeyError, IndexError) as e:
        raise LLMError(f"YandexGPT response parse error: {e}, body: {resp.text[:500]}")


# ── Ollama call ─────────────────────────────────────────────────

def _call_ollama(messages: list[dict], max_tokens: int = 2500, temperature: float = 0.1,
                 json_mode: bool = True) -> str:
    """Call Ollama with OpenAI-compatible API."""
    url = f"{OLLAMA_BASE}/v1/chat/completions"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        with httpx.Client(timeout=180) as client:
            resp = client.post(url, json=payload)
        if resp.status_code != 200:
            raise LLMError(f"Ollama error {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except httpx.ConnectError:
        raise LLMError(f"Cannot connect to Ollama at {OLLAMA_BASE}")


# ── Unified interface ───────────────────────────────────────────

def extract_graph(chunk_text: str) -> dict:
    """Extract entities, relations, experiments from text."""
    if PROVIDER == "mock":
        return {
            "entities": [
                {"name": "Мок-Материал", "type": "Material", "description": "Материал для тестов", "aliases": ["mock_material", "тестовый материал"]},
                {"name": "Мок-Процесс", "type": "Process", "description": "Процесс для тестов", "aliases": ["mock_process"]},
                {"name": "Мок-Оборудование", "type": "Equipment", "description": "Оборудование для тестов", "aliases": ["mock_equipment"]}
            ],
            "relations": [
                {"source": "Мок-Процесс", "target": "Мок-Материал", "type": "USES_MATERIAL"}
            ],
            "experiments": [{
                "name": "Мок-Эксперимент 1",
                "source": {"document_id": "mock_doc", "chunk_id": "mock_chunk", "original_text": chunk_text[:100]},
                "uses_materials": ["Мок-Материал"],
                "uses_processes": ["Мок-Процесс"],
                "performed_at": "Мок-Лаборатория",
                "produces_output": [{
                    "property": "temperature",
                    "value_min": 150.0,
                    "value_max": 250.0,
                    "unit": "°C",
                    "geography": "Russia",
                    "time": "2024"
                }, {
                    "property": "pressure",
                    "value_min": 10.0,
                    "value_max": 10.0,
                    "unit": "atm",
                    "geography": "world",
                    "time": "2023"
                }]
            }]
        }
    elif PROVIDER == "yandex":
        content = _call_yandex(chunk_text[:8000])
    else:
        content = _call_ollama([
            {"role": "system", "content": EXTRACTION_SYSTEM},
            {"role": "user", "content": chunk_text[:8000]},
        ])
    # Try to parse JSON from response (YandexGPT may wrap in markdown)
    try:
        # Strip any markdown code fences
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if "```" in cleaned:
                cleaned = cleaned.rsplit("```", 1)[0]
        data = json.loads(cleaned.strip())
    except json.JSONDecodeError:
        # Fallback: try to find JSON in the response
        import re
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}
    return {
        "entities": data.get("entities") or [],
        "relations": data.get("relations") or [],
        "experiments": data.get("experiments") or [],
    }


def answer_question(question: str, context: str, history: list[dict] | None = None) -> str:
    """Answer a question using graph context and chat history."""
    if PROVIDER == "mock":
        return f"**[MOCK ОТВЕТ]**\nВы спросили: *{question}*\n\nЯ моковый LLM провайдер. Я вижу контекст длиной {len(context)} символов.\n\nСудя по графу, Мок-Эксперимент 1 показал температуру 150-250 °C. Противоречий не найдено."
        
    if PROVIDER == "yandex":
        return _call_yandex(
            f"КОНТЕКСТ ИЗ ГРАФА ЗНАНИЙ:\n{context}\n\nВОПРОС: {question}",
            max_tokens=1200, temperature=0.3,
            system_prompt=CHAT_SYSTEM,
            history=history,
        )
    
    msgs = [{"role": "system", "content": CHAT_SYSTEM}]
    if history:
        for h in history:
            msgs.append({"role": h["role"], "content": h["content"]})
    msgs.append({"role": "user", "content": f"КОНТЕКСТ ИЗ ГРАФА ЗНАНИЙ:\n{context}\n\nВОПРОС: {question}"})
    return _call_ollama(msgs, max_tokens=1200, temperature=0.3)


def classify_region(text: str) -> str:
    """Classify text as 'RU', 'world', or 'unknown' using LLM."""
    if PROVIDER == "mock":
        return "unknown"
    try:
        if PROVIDER == "yandex":
            result = _call_yandex(
                f"Определи регион исследования:\n\n{text[:2000]}",
                max_tokens=100, temperature=0.0,
                system_prompt=REGION_SYSTEM,
            )
        else:
            result = _call_ollama([
                {"role": "system", "content": REGION_SYSTEM},
                {"role": "user", "content": f"Определи регион исследования:\n\n{text[:2000]}"},
            ], max_tokens=100, temperature=0.0)

        import json
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if "```" in cleaned:
                cleaned = cleaned.rsplit("```", 1)[0]
        data = json.loads(cleaned.strip())
        region = data.get("region", "unknown")
        if region in ("RU", "world", "unknown"):
            return region
        return "unknown"
    except Exception as e:
        logger.warning("Region classification failed: %s", e)
        return "unknown"


def check_health() -> dict:
    """Check if LLM provider is reachable."""
    if PROVIDER == "mock":
        return {"ok": True, "provider": "mock", "model": "mock-llm-v1"}
    elif PROVIDER == "yandex":
        if YANDEX_API_KEY and YANDEX_FOLDER_ID:
            return {"ok": True, "provider": "yandex", "model": YANDEX_MODEL}
        return {"ok": False, "error": "YANDEX_API_KEY or YANDEX_FOLDER_ID not set"}
    else:
        try:
            models = _list_ollama_models()
            return {"ok": True, "provider": "ollama", "models": models, "selected": OLLAMA_MODEL}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}


def _list_ollama_models() -> list[str]:
    """List available Ollama models."""
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{OLLAMA_BASE}/api/tags")
        if resp.status_code == 200:
            return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        pass
    return []


def list_models() -> list[str]:
    """List available models from the active provider."""
    if PROVIDER == "mock":
        return ["mock:mock-llm-v1"]
    elif PROVIDER == "yandex":
        return [f"yandex:{YANDEX_MODEL}"]
    return [f"ollama:{m}" for m in _list_ollama_models()]


# ── Re-export for backwards compat ─────────────────────────────
OLLAMA_BASE_URL = OLLAMA_BASE
OLLAMA_MODEL_NAME = OLLAMA_MODEL
