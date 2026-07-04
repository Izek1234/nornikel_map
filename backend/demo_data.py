"""In-memory demo data for NORNIKEL Knowledge Map.

Provides pre-seeded entities (60+), facts (80+), relations, experts, publications,
facilities and experiments — all nickel-metallurgy domain. Used when Neo4j is not
configured (DEMO mode).

GraphRAG in demo mode:
  ask()        – full pipeline: token match → 2-hop entity expansion → fact scoring
                 → structured answer.
  get_rag_context()   – returns raw context dict (entities, facts, chunks).
  get_comparison()    – side-by-side comparison of two topics.
  get_knowledge_gaps()– areas with few facts / low confidence.

CAG in demo mode: module-level LRU dict (max 100 entries, TTL 7 days).
"""

from __future__ import annotations

import hashlib
import re
import time
from collections import OrderedDict
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# CAG: in-memory LRU cache (module-level, survives across requests)
# ─────────────────────────────────────────────────────────────────────────────

_CACHE_TTL = 60 * 60 * 24 * 7   # 7 days
_CACHE_MAX  = 100
_CACHE_HITS = 0
_CACHE_REQS = 0

_lru_cache: OrderedDict[str, dict] = OrderedDict()  # key -> {data, ts}


def _cache_key(question: str) -> str:
    normalized = re.sub(r"\s+", " ", question.strip().lower())
    normalized = re.sub(r"[^\wа-яё%°/.,\- ]", " ", normalized)
    return hashlib.sha256(normalized.encode()).hexdigest()


def _cache_get(question: str) -> dict | None:
    global _CACHE_HITS, _CACHE_REQS
    _CACHE_REQS += 1
    k = _cache_key(question)
    if k in _lru_cache:
        entry = _lru_cache[k]
        if time.time() - entry["ts"] < _CACHE_TTL:
            _CACHE_HITS += 1
            _lru_cache.move_to_end(k)
            return entry["data"]
        else:
            del _lru_cache[k]
    return None


def _cache_put(question: str, data: dict) -> None:
    k = _cache_key(question)
    _lru_cache[k] = {"data": data, "ts": time.time()}
    _lru_cache.move_to_end(k)
    while len(_lru_cache) > _CACHE_MAX:
        _lru_cache.popitem(last=False)


def get_cache_stats() -> dict:
    hit_rate = round(_CACHE_HITS / max(_CACHE_REQS, 1), 3)
    return {
        "total_entries": len(_lru_cache),
        "hit_rate": hit_rate,
        "hits": _CACHE_HITS,
        "requests": _CACHE_REQS,
        "avg_similarity": 1.0,
        "mode": "demo_memory",
    }


def clear_cache() -> dict:
    global _CACHE_HITS, _CACHE_REQS
    _lru_cache.clear()
    _CACHE_HITS = 0
    _CACHE_REQS = 0
    return {"ok": True, "cleared": True}


# ─────────────────────────────────────────────────────────────────────────────
# ENTITY CATALOGUE  (60+ entities)
# ─────────────────────────────────────────────────────────────────────────────

ENTITIES: list[dict] = [
    # ── Materials ──────────────────────────────────────────────
    {"key": "никель",           "name": "Никель",               "type": "Material",   "description": "Ni, основной продукт Норникеля; нержавеющая сталь, EV-батареи"},
    {"key": "медь",             "name": "Медь",                 "type": "Material",   "description": "Cu, попутный цветной металл, извлекается параллельно с Ni"},
    {"key": "кобальт",          "name": "Кобальт",              "type": "Material",   "description": "Co, ценный попутный металл; спрос растёт из-за EV-батарей"},
    {"key": "мпг",              "name": "МПГ",                  "type": "Material",   "description": "Металлы платиновой группы: Pt, Pd, Rh, Ru, Ir, Os"},
    {"key": "платина",          "name": "Платина",              "type": "Material",   "description": "Pt, драгоценный МПГ; автокатализаторы, ювелирная промышленность"},
    {"key": "палладий",         "name": "Палладий",             "type": "Material",   "description": "Pd, самый распространённый МПГ в рудах Норникеля; автокатализаторы"},
    {"key": "родий",            "name": "Родий",                "type": "Material",   "description": "Rh, редчайший МПГ; цена выше золота; трёхкомпонентные катализаторы"},
    {"key": "рутений",          "name": "Рутений",              "type": "Material",   "description": "Ru, МПГ; электроника и химический катализ"},
    {"key": "штейн",            "name": "Штейн",                "type": "Material",   "description": "Промежуточный продукт плавки; сульфидный расплав Ni-Cu-Co-МПГ"},
    {"key": "конвертерный шлак","name": "Конвертерный шлак",   "type": "Material",   "description": "Шлак конвертерной плавки; содержит остаточные металлы"},
    {"key": "шлак",             "name": "Шлак",                 "type": "Material",   "description": "Отход плавки, силикатный расплав"},
    {"key": "серная кислота",   "name": "Серная кислота",       "type": "Material",   "description": "H2SO4, реагент выщелачивания и электролита"},
    {"key": "электролит",       "name": "Электролит",           "type": "Material",   "description": "Водный раствор солей Ni; среда для электроэкстракции"},
    {"key": "католит",          "name": "Католит",              "type": "Material",   "description": "Электролит катодного пространства; содержит Ni2+"},
    {"key": "анолит",           "name": "Анолит",               "type": "Material",   "description": "Электролит анодного пространства; накапливает H2SO4"},
    {"key": "гипс",             "name": "Гипс",                 "type": "Material",   "description": "CaSO4·2H2O; техногенный гипс — продукт нейтрализации стоков"},
    {"key": "хвосты",           "name": "Хвосты",               "type": "Material",   "description": "Отходы флотационного обогащения"},
    {"key": "сульфаты",         "name": "Сульфаты",             "type": "Property",   "description": "SO4(2-) ионы; ключевой показатель качества сточных вод"},
    {"key": "хлориды",          "name": "Хлориды",              "type": "Property",   "description": "Cl(-) ионы; ускоряют коррозию при избытке"},
    {"key": "пероксид водорода","name": "Пероксид водорода",    "type": "Material",   "description": "H2O2; окислитель при автоклавном выщелачивании"},
    {"key": "известь",          "name": "Известь",              "type": "Material",   "description": "CaO/Ca(OH)2; нейтрализатор кислотных стоков"},
    {"key": "флотореагент",     "name": "Флотореагент",         "type": "Material",   "description": "Собиратели и пенообразователи для флотации сульфидов"},
    {"key": "анод никелевый",   "name": "Анод никелевый",       "type": "Material",   "description": "Никелевый анод для электролитического рафинирования"},
    {"key": "катод никелевый",  "name": "Катод никелевый",      "type": "Material",   "description": "Чистый никелевый катод — товарный продукт электролиза"},
    {"key": "концентрат",       "name": "Концентрат",           "type": "Material",   "description": "Флотационный концентрат сульфидов Ni-Cu"},
    {"key": "файнштейн",        "name": "Файнштейн",            "type": "Material",   "description": "Конвертированный штейн с высоким Ni+Cu (>70%)"},
    {"key": "диоксид серы",     "name": "Диоксид серы",         "type": "Material",   "description": "SO2, газ плавки; улавливается и конвертируется в H2SO4"},

    # ── Processes ──────────────────────────────────────────────
    {"key": "электроэкстракция",       "name": "Электроэкстракция",       "type": "Process", "description": "Электролитическое осаждение металла из раствора (EW)"},
    {"key": "электролиз",              "name": "Электролиз",              "type": "Process", "description": "Электрохимическое рафинирование никеля"},
    {"key": "выщелачивание",           "name": "Выщелачивание",           "type": "Process", "description": "Перевод металлов из твёрдой фазы в раствор реагентом"},
    {"key": "автоклавное выщелачивание","name": "Автоклавное выщелачивание","type": "Process","description": "POX — выщелачивание под давлением O2 при 220-260 C"},
    {"key": "флотация",                "name": "Флотация",                "type": "Process", "description": "Обогащение руды методом пенной флотации сульфидов"},
    {"key": "взвешенная плавка",       "name": "Взвешенная плавка",       "type": "Process", "description": "Flash smelting — плавка сульфидного концентрата во взвешенном состоянии"},
    {"key": "конвертирование",         "name": "Конвертирование",         "type": "Process", "description": "Продувка штейна воздухом/O2 для окисления Fe и S"},
    {"key": "обессоливание",           "name": "Обессоливание",           "type": "Process", "description": "Удаление солей из промывных и сточных вод"},
    {"key": "обратный осмос",          "name": "Обратный осмос",          "type": "Process", "description": "Мембранная фильтрация под давлением; RO"},
    {"key": "ионный обмен",            "name": "Ионный обмен",            "type": "Process", "description": "Глубокая деионизация воды смолами"},
    {"key": "электродиализ",           "name": "Электродиализ",           "type": "Process", "description": "Мембранное разделение под действием электрического поля"},
    {"key": "нейтрализация",           "name": "Нейтрализация",           "type": "Process", "description": "Осаждение металлов и нейтрализация кислоты известью"},
    {"key": "дробление",               "name": "Дробление",               "type": "Process", "description": "Механическое измельчение руды"},
    {"key": "сгущение",                "name": "Сгущение",                "type": "Process", "description": "Сгущение пульпы перед фильтрацией"},
    {"key": "фильтрация",              "name": "Фильтрация",              "type": "Process", "description": "Разделение твёрдого и жидкого"},
    {"key": "жидкостная экстракция",   "name": "Жидкостная экстракция",   "type": "Process", "description": "SX — экстракция металлов органическим растворителем"},
    {"key": "конверсия со2",           "name": "Конверсия SO2",           "type": "Process", "description": "Каталитическое окисление SO2 в серную кислоту"},

    # ── Equipment ──────────────────────────────────────────────
    {"key": "ванна электроэкстракции", "name": "Ванна электроэкстракции", "type": "Equipment", "description": "Электролизная ванна для EW Ni или Cu"},
    {"key": "диафрагменная ячейка",    "name": "Диафрагменная ячейка",    "type": "Equipment", "description": "Ячейка с ионообменной мембраной"},
    {"key": "печь взвешенной плавки",  "name": "Печь взвешенной плавки",  "type": "Equipment", "description": "ПВП — агрегат flash smelting"},
    {"key": "конвертер",               "name": "Конвертер",               "type": "Equipment", "description": "Конвертер Пирс-Смита для конвертирования штейна"},
    {"key": "автоклав",                "name": "Автоклав",                "type": "Equipment", "description": "Горизонтальный или вертикальный автоклав для POX"},
    {"key": "мембранный модуль",       "name": "Мембранный модуль",       "type": "Equipment", "description": "RO-/NF-модуль для обессоливания сточных вод"},
    {"key": "система очистки газов",   "name": "Система очистки газов",   "type": "Equipment", "description": "Мокрая/сухая очистка газов от SO2 и пыли"},
    {"key": "фильтр-пресс",            "name": "Фильтр-пресс",            "type": "Equipment", "description": "Рамный фильтр-пресс для обезвоживания осадков"},
    {"key": "ионообменная колонна",    "name": "Ионообменная колонна",    "type": "Equipment", "description": "Колонна с катионитом/анионитом"},

    # ── Facilities ─────────────────────────────────────────────
    {"key": "норникель",   "name": "Норникель",       "type": "Facility", "description": "ПАО ГМК Норильский никель — крупнейший производитель Ni, Pd"},
    {"key": "надежда",     "name": "Завод Надежда",   "type": "Facility", "description": "Металлургический завод Надежда, г. Норильск; электролиз Ni, Cu"},
    {"key": "комсомольский","name": "Рудник Комсомольский","type": "Facility","description": "Подземный рудник Комсомольский; добыча медно-никелевых руд"},
    {"key": "медный завод","name": "Медный завод",    "type": "Facility", "description": "Норильский медный завод; конвертирование и электролиз меди"},
    {"key": "кольская гмк","name": "Кольская ГМК",   "type": "Facility", "description": "Кольская ГМК; рафинирование Ni, Co"},
    {"key": "цниирмо",     "name": "ЦНИИРМО",         "type": "Facility", "description": "Центральный НИИ рудо-металлургии и обогащения; R&D"},
    {"key": "гипроникель", "name": "Гипроникель",     "type": "Facility", "description": "Институт Гипроникель — ключевой проектный НИИ Норникеля"},

    # ── Experts ────────────────────────────────────────────────
    {"key": "востриков",  "name": "Востриков Н.М.",  "type": "Expert", "description": "Ведущий специалист по гидрометаллургии Ni; д.т.н."},
    {"key": "лебедев",    "name": "Лебедев В.А.",    "type": "Expert", "description": "Специалист по электрохимическим процессам извлечения металлов"},
    {"key": "иванов",     "name": "Иванов С.П.",     "type": "Expert", "description": "Технолог обессоливания и водоподготовки; к.т.н."},
    {"key": "петров",     "name": "Петров О.Г.",     "type": "Expert", "description": "Специалист по пирометаллургии; взвешенная плавка"},
    {"key": "сидорова",   "name": "Сидорова Е.Н.",   "type": "Expert", "description": "Эколог; утилизация газов и сточных вод металлургических предприятий"},
    {"key": "кузнецов",   "name": "Кузнецов А.В.",   "type": "Expert", "description": "Гидрометаллург; автоклавное выщелачивание сульфидных концентратов"},
    {"key": "морозов",    "name": "Морозов Д.Л.",    "type": "Expert", "description": "Специалист по флотационному обогащению никелевых руд"},

    # ── Publications ───────────────────────────────────────────
    {"key": "pub_gp1_2024",    "name": "ГП №1-2024",              "type": "Publication", "description": "Годовой план R&D 2024: электроэкстракция, водоподготовка"},
    {"key": "pub_gp2_2024",    "name": "ГП №2-2024",              "type": "Publication", "description": "Годовой план R&D 2024: флотация, POX, экология"},
    {"key": "pub_vostrikova",  "name": "Доклад Вострикова 2023", "type": "Publication", "description": "Оптимизация режима электроэкстракции Ni; Гипроникель 2023"},
    {"key": "pub_pox_review",  "name": "Обзор POX 2022",         "type": "Publication", "description": "Мировая практика автоклавного выщелачивания сульфидных Ni-концентратов"},
    {"key": "pub_water_2023",  "name": "Водоподготовка 2023",    "type": "Publication", "description": "Обезвреживание сточных вод медно-никелевого производства"},
    {"key": "pub_flotation",   "name": "Флотация 2021",          "type": "Publication", "description": "Реагентный режим флотации вкрапленных норильских руд"},
    {"key": "pub_ecology_2024","name": "Экологический отчёт 2024","type": "Publication","description": "Снижение выбросов SO2 и сбросов: результаты 2020-2024"},

    # ── Experiments ────────────────────────────────────────────
    {"key": "exp_ew_ni",       "name": "Эксперимент ЭЭ Ni",        "type": "Experiment", "description": "Оптимизация электроэкстракции Ni при переменной плотности тока"},
    {"key": "exp_pox_ni",      "name": "Эксперимент POX Ni",       "type": "Experiment", "description": "Автоклавное выщелачивание Ni-концентрата с добавкой H2O2"},
    {"key": "exp_ro_desalt",   "name": "Эксперимент РО обессол.",  "type": "Experiment", "description": "Испытание RO-установки для обессоливания промывных вод"},
    {"key": "exp_flotation",   "name": "Эксперимент флотация",    "type": "Experiment", "description": "Пилотная флотация руды нового участка Комсомольского"},
    {"key": "exp_pgm_dist",    "name": "Эксперимент МПГ-штейн",   "type": "Experiment", "description": "Распределение МПГ между штейном и шлаком при ПВП"},
    {"key": "exp_sx_co",       "name": "Эксперимент SX Кобальт",  "type": "Experiment", "description": "Жидкостная экстракция Co из никелевого электролита"},
    {"key": "exp_neutraliz",   "name": "Эксперимент нейтрализация","type": "Experiment","description": "Нейтрализация кислотных стоков известью"},
]


# ─────────────────────────────────────────────────────────────────────────────
# FACTS CATALOGUE  (80+ facts)
# ─────────────────────────────────────────────────────────────────────────────

FACTS: list[dict] = [
    # ── Электроэкстракция ─────────────────────────────────────
    {"subject": "Электроэкстракция", "predicate": "извлечение никеля",
     "value_min": 95.0, "value_max": 98.5, "unit": "%", "unit_normalized": "%",
     "object": "сквозное извлечение Ni", "geography": "world", "confidence": 0.90,
     "source_doc": "pub_vostrikova",
     "quote": "Степень извлечения Ni при электроэкстракции составляет 95-98,5%"},

    {"subject": "Электроэкстракция", "predicate": "извлечение никеля (РФ лучшая практика)",
     "value_min": 96.0, "value_max": 98.0, "unit": "%", "unit_normalized": "%",
     "object": "лучшая практика РФ", "geography": "RU", "confidence": 0.88,
     "source_doc": "pub_vostrikova",
     "quote": "Российские заводы достигают 96-98% при оптимизированном режиме"},

    {"subject": "Электроэкстракция", "predicate": "плотность тока",
     "value_min": 200.0, "value_max": 300.0, "unit": "A/m2", "unit_normalized": "A/m2",
     "object": "рабочий диапазон", "geography": "world", "confidence": 0.85,
     "source_doc": "pub_vostrikova",
     "quote": "Оптимальная плотность тока 200-300 А/м2"},

    {"subject": "Электроэкстракция", "predicate": "удельный расход электроэнергии",
     "value_min": 2200.0, "value_max": 2800.0, "unit": "kWh/t", "unit_normalized": "kWh/t",
     "object": "энергопотребление мировая практика", "geography": "world", "confidence": 0.82,
     "source_doc": "pub_gp1_2024",
     "quote": "Удельное энергопотребление EW Ni: 2200-2800 кВт·ч/т"},

    {"subject": "Электроэкстракция", "predicate": "удельный расход электроэнергии (РФ)",
     "value_min": 2400.0, "value_max": 3100.0, "unit": "kWh/t", "unit_normalized": "kWh/t",
     "object": "устаревшее оборудование РФ", "geography": "RU", "confidence": 0.78,
     "source_doc": "pub_gp1_2024",
     "quote": "Старые ванны РФ потребляют 2400-3100 кВт·ч/т из-за устаревших катодов"},

    {"subject": "Электроэкстракция", "predicate": "pH католита",
     "value_min": 2.5, "value_max": 4.5, "unit": "pH", "unit_normalized": "pH",
     "object": "диапазон pH", "geography": "world", "confidence": 0.80,
     "source_doc": "pub_vostrikova",
     "quote": "pH католита поддерживается в диапазоне 2,5-4,5"},

    {"subject": "Электроэкстракция", "predicate": "температура электролита",
     "value_min": 55.0, "value_max": 70.0, "unit": "degC", "unit_normalized": "degC",
     "object": "рабочая температура", "geography": "world", "confidence": 0.80,
     "source_doc": "pub_gp1_2024",
     "quote": "Рабочая температура электролита 55-70 С"},

    {"subject": "Электроэкстракция", "predicate": "концентрация Ni в электролите",
     "value_min": 60.0, "value_max": 100.0, "unit": "g/L", "unit_normalized": "g/L",
     "object": "Ni2+ в католите", "geography": "world", "confidence": 0.83,
     "source_doc": "pub_vostrikova",
     "quote": "Концентрация Ni2+ в католите 60-100 г/л"},

    {"subject": "Католит", "predicate": "скорость циркуляции",
     "value_min": 0.5, "value_max": 1.5, "unit": "m3/h", "unit_normalized": "m3/h",
     "object": "расход подачи", "geography": "world", "confidence": 0.75,
     "source_doc": "pub_gp1_2024",
     "quote": "Скорость циркуляции католита 0,5-1,5 м3/ч"},

    {"subject": "Ванна электроэкстракции", "predicate": "рабочее напряжение",
     "value_min": 2.0, "value_max": 4.5, "unit": "V", "unit_normalized": "V",
     "object": "вольтаж ванны", "geography": "world", "confidence": 0.75,
     "source_doc": "pub_vostrikova",
     "quote": "Рабочее напряжение ванны ЭЭ 2,0-4,5 В"},

    # ── Автоклавное выщелачивание ─────────────────────────────
    {"subject": "Автоклавное выщелачивание", "predicate": "температура",
     "value_min": 220.0, "value_max": 260.0, "unit": "degC", "unit_normalized": "degC",
     "object": "рабочая температура POX мировая", "geography": "world", "confidence": 0.88,
     "source_doc": "pub_pox_review",
     "quote": "Температура автоклавного выщелачивания 220-260 С (мировая практика)"},

    {"subject": "Автоклавное выщелачивание", "predicate": "температура (Норникель)",
     "value_min": 225.0, "value_max": 245.0, "unit": "degC", "unit_normalized": "degC",
     "object": "рабочая температура Норникель", "geography": "RU", "confidence": 0.86,
     "source_doc": "pub_gp2_2024",
     "quote": "Норникель применяет POX при 225-245 С для Ni-концентрата"},

    {"subject": "Автоклавное выщелачивание", "predicate": "давление O2",
     "value_min": 0.5, "value_max": 1.5, "unit": "MPa", "unit_normalized": "MPa",
     "object": "парциальное давление кислорода", "geography": "world", "confidence": 0.85,
     "source_doc": "pub_pox_review",
     "quote": "Парциальное давление O2 0,5-1,5 МПа"},

    {"subject": "Автоклавное выщелачивание", "predicate": "извлечение никеля",
     "value_min": 96.0, "value_max": 99.0, "unit": "%", "unit_normalized": "%",
     "object": "сквозное извлечение Ni POX", "geography": "world", "confidence": 0.88,
     "source_doc": "pub_pox_review",
     "quote": "Сквозное извлечение Ni при POX 96-99%"},

    {"subject": "Автоклавное выщелачивание", "predicate": "извлечение кобальта",
     "value_min": 93.0, "value_max": 97.5, "unit": "%", "unit_normalized": "%",
     "object": "сквозное извлечение Co POX", "geography": "world", "confidence": 0.85,
     "source_doc": "pub_pox_review",
     "quote": "Извлечение Co 93-97,5% при оптимальном режиме"},

    {"subject": "Автоклавное выщелачивание", "predicate": "расход H2SO4",
     "value_min": 180.0, "value_max": 350.0, "unit": "kg/t", "unit_normalized": "kg/t",
     "object": "удельный расход кислоты", "geography": "world", "confidence": 0.80,
     "source_doc": "pub_pox_review",
     "quote": "Удельный расход H2SO4 180-350 кг/т концентрата"},

    {"subject": "Автоклавное выщелачивание", "predicate": "время выщелачивания",
     "value_min": 1.0, "value_max": 3.0, "unit": "h", "unit_normalized": "h",
     "object": "время пребывания в автоклаве", "geography": "world", "confidence": 0.80,
     "source_doc": "pub_pox_review",
     "quote": "Время пребывания пульпы в автоклаве 1-3 часа"},

    # ── Взвешенная плавка ─────────────────────────────────────
    {"subject": "Взвешенная плавка", "predicate": "температура",
     "value_min": 1250.0, "value_max": 1350.0, "unit": "degC", "unit_normalized": "degC",
     "object": "температура реакционного вала", "geography": "world", "confidence": 0.87,
     "source_doc": "pub_gp2_2024",
     "quote": "Температура в реакционном вале ПВП 1250-1350 С"},

    {"subject": "Взвешенная плавка", "predicate": "содержание никеля в штейне",
     "value_min": 60.0, "value_max": 75.0, "unit": "wt%", "unit_normalized": "wt%",
     "object": "Ni в штейне", "geography": "RU", "confidence": 0.85,
     "source_doc": "pub_gp2_2024",
     "quote": "Содержание Ni в штейне ПВП Норникеля 60-75 мас.%"},

    {"subject": "Взвешенная плавка", "predicate": "извлечение никеля в штейн",
     "value_min": 94.0, "value_max": 97.5, "unit": "%", "unit_normalized": "%",
     "object": "Ni в штейн при плавке", "geography": "world", "confidence": 0.87,
     "source_doc": "pub_gp2_2024",
     "quote": "Извлечение Ni в штейн при взвешенной плавке 94-97,5%"},

    {"subject": "Взвешенная плавка", "predicate": "содержание SO2 в газе",
     "value_min": 10.0, "value_max": 25.0, "unit": "vol%", "unit_normalized": "vol%",
     "object": "SO2 отходящий газ", "geography": "world", "confidence": 0.82,
     "source_doc": "pub_ecology_2024",
     "quote": "Содержание SO2 в отходящих газах ПВП 10-25 об.%"},

    {"subject": "Печь взвешенной плавки", "predicate": "производительность",
     "value_min": 1000.0, "value_max": 3000.0, "unit": "t/day", "unit_normalized": "t/day",
     "object": "тоннаж сухого концентрата", "geography": "world", "confidence": 0.78,
     "source_doc": "pub_gp2_2024",
     "quote": "Производительность ПВП 1000-3000 т/сут сухого концентрата"},

    # ── Флотация ──────────────────────────────────────────────
    {"subject": "Флотация", "predicate": "извлечение никеля",
     "value_min": 85.0, "value_max": 92.0, "unit": "%", "unit_normalized": "%",
     "object": "Ni во флотационный концентрат", "geography": "RU", "confidence": 0.82,
     "source_doc": "pub_flotation",
     "quote": "Извлечение Ni при флотации норильских руд 85-92%"},

    {"subject": "Флотация", "predicate": "извлечение меди",
     "value_min": 88.0, "value_max": 95.0, "unit": "%", "unit_normalized": "%",
     "object": "Cu во флотационный концентрат", "geography": "RU", "confidence": 0.80,
     "source_doc": "pub_flotation",
     "quote": "Извлечение Cu при флотации 88-95%"},

    {"subject": "Флотация", "predicate": "содержание Ni в концентрате",
     "value_min": 8.0, "value_max": 14.0, "unit": "wt%", "unit_normalized": "wt%",
     "object": "Ni в флотоконцентрате", "geography": "RU", "confidence": 0.80,
     "source_doc": "pub_flotation",
     "quote": "Содержание Ni в флотоконцентрате 8-14 мас.%"},

    {"subject": "Флотация", "predicate": "расход флотореагентов",
     "value_min": 80.0, "value_max": 200.0, "unit": "g/t", "unit_normalized": "g/t",
     "object": "собиратели + пенообразователь", "geography": "RU", "confidence": 0.75,
     "source_doc": "pub_flotation",
     "quote": "Расход флотореагентов 80-200 г/т руды"},

    {"subject": "Флотация", "predicate": "крупность помола класс -0,074 мм",
     "value_min": 65.0, "value_max": 80.0, "unit": "%", "unit_normalized": "%",
     "object": "доля класса минус 74 мкм", "geography": "RU", "confidence": 0.78,
     "source_doc": "pub_flotation",
     "quote": "Оптимальная крупность: 65-80% класса -0,074 мм"},

    # ── МПГ ───────────────────────────────────────────────────
    {"subject": "Штейн", "predicate": "содержание МПГ",
     "value_min": 85.0, "value_max": 95.0, "unit": "%", "unit_normalized": "%",
     "object": "доля МПГ в штейне от исходного", "geography": "RU", "confidence": 0.85,
     "source_doc": "pub_gp2_2024",
     "quote": "85-95% МПГ из руды концентрируется в штейне при плавке"},

    {"subject": "Шлак", "predicate": "содержание МПГ (потери)",
     "value_min": 3.0, "value_max": 8.0, "unit": "g/t", "unit_normalized": "g/t",
     "object": "потери МПГ со шлаком", "geography": "world", "confidence": 0.80,
     "source_doc": "pub_gp2_2024",
     "quote": "Потери МПГ со шлаком 3-8 г/т шлака"},

    {"subject": "Палладий", "predicate": "содержание в норильских рудах",
     "value_min": 2.0, "value_max": 5.0, "unit": "g/t", "unit_normalized": "g/t",
     "object": "Pd в исходной руде", "geography": "RU", "confidence": 0.82,
     "source_doc": "pub_gp2_2024",
     "quote": "Содержание Pd в норильских рудах 2-5 г/т"},

    {"subject": "Платина", "predicate": "содержание в норильских рудах",
     "value_min": 0.5, "value_max": 2.0, "unit": "g/t", "unit_normalized": "g/t",
     "object": "Pt в исходной руде", "geography": "RU", "confidence": 0.82,
     "source_doc": "pub_gp2_2024",
     "quote": "Содержание Pt в норильских рудах 0,5-2,0 г/т"},

    {"subject": "МПГ", "predicate": "суммарное извлечение Pd+Pt",
     "value_min": 88.0, "value_max": 93.0, "unit": "%", "unit_normalized": "%",
     "object": "Pd+Pt из руды в товар", "geography": "RU", "confidence": 0.87,
     "source_doc": "pub_gp2_2024",
     "quote": "Суммарное извлечение МПГ (Pd+Pt) в товарную продукцию 88-93%"},

    # ── Обессоливание / водоподготовка ────────────────────────
    {"subject": "Обратный осмос", "predicate": "сухой остаток после обработки",
     "value_min": None, "value_max": 500.0, "unit": "mg/L", "unit_normalized": "mg/L",
     "object": "очищенная вода", "geography": "world", "confidence": 0.80,
     "source_doc": "pub_water_2023",
     "quote": "Обратный осмос снижает сухой остаток до <= 500 мг/л"},

    {"subject": "Ионный обмен", "predicate": "сухой остаток после обработки",
     "value_min": None, "value_max": 50.0, "unit": "mg/L", "unit_normalized": "mg/L",
     "object": "деионизированная вода", "geography": "world", "confidence": 0.82,
     "source_doc": "pub_water_2023",
     "quote": "Ионный обмен обеспечивает сухой остаток <= 50 мг/л"},

    {"subject": "Обратный осмос", "predicate": "удаление сульфатов",
     "value_min": 92.0, "value_max": 98.0, "unit": "%", "unit_normalized": "%",
     "object": "SO4(2-) rejection", "geography": "world", "confidence": 0.83,
     "source_doc": "pub_water_2023",
     "quote": "Мембраны RO удаляют 92-98% сульфатов"},

    {"subject": "Электродиализ", "predicate": "удаление сульфатов",
     "value_min": 85.0, "value_max": 95.0, "unit": "%", "unit_normalized": "%",
     "object": "SO4(2-) при ED", "geography": "world", "confidence": 0.75,
     "source_doc": "pub_water_2023",
     "quote": "Электродиализ удаляет 85-95% сульфатов"},

    {"subject": "Обессоливание", "predicate": "эффективность при SO4 200-300 мг/л",
     "value_min": 90.0, "value_max": 99.0, "unit": "%", "unit_normalized": "%",
     "object": "снижение солесодержания", "geography": "RU", "confidence": 0.78,
     "source_doc": "pub_water_2023",
     "quote": "Эффективность обессоливания при исходных сульфатах 200-300 мг/л составляет 90-99%"},

    {"subject": "Сульфаты", "predicate": "норматив сброса",
     "value_min": None, "value_max": 500.0, "unit": "mg/L", "unit_normalized": "mg/L",
     "object": "ПДК SO4(2-) рыбохоз. водоём", "geography": "RU", "confidence": 0.88,
     "source_doc": "pub_water_2023",
     "quote": "ПДК SO4(2-) для рыбохозяйственных водоёмов <= 500 мг/л"},

    {"subject": "Хлориды", "predicate": "норматив сброса",
     "value_min": None, "value_max": 300.0, "unit": "mg/L", "unit_normalized": "mg/L",
     "object": "ПДК Cl(-) сброс", "geography": "RU", "confidence": 0.85,
     "source_doc": "pub_water_2023",
     "quote": "ПДК Cl(-) для рыбохозяйственных водоёмов <= 300 мг/л"},

    {"subject": "Мембранный модуль", "predicate": "рабочее давление",
     "value_min": 1.0, "value_max": 7.0, "unit": "MPa", "unit_normalized": "MPa",
     "object": "давление подачи RO", "geography": "world", "confidence": 0.80,
     "source_doc": "pub_water_2023",
     "quote": "Рабочее давление RO-мембранных модулей 1-7 МПа"},

    # ── Экология ──────────────────────────────────────────────
    {"subject": "Диоксид серы", "predicate": "выброс до Серной программы",
     "value_min": 1900.0, "value_max": 2200.0, "unit": "kt/year", "unit_normalized": "kt/year",
     "object": "выбросы SO2 2015-2019", "geography": "RU", "confidence": 0.90,
     "source_doc": "pub_ecology_2024",
     "quote": "Выбросы SO2 до Серной программы: 1900-2200 кт/год"},

    {"subject": "Диоксид серы", "predicate": "выброс после Серной программы",
     "value_min": 900.0, "value_max": 1100.0, "unit": "kt/year", "unit_normalized": "kt/year",
     "object": "выбросы SO2 2023-2024", "geography": "RU", "confidence": 0.87,
     "source_doc": "pub_ecology_2024",
     "quote": "После Серной программы выбросы снижены до 900-1100 кт/год"},

    {"subject": "Конверсия SO2", "predicate": "степень улавливания SO2",
     "value_min": 95.0, "value_max": 99.5, "unit": "%", "unit_normalized": "%",
     "object": "улавливание SO2 каталитическими установками", "geography": "world",
     "confidence": 0.87, "source_doc": "pub_ecology_2024",
     "quote": "Каталитические установки улавливают 95-99,5% SO2"},

    # ── Конвертирование ───────────────────────────────────────
    {"subject": "Конвертирование", "predicate": "температура конвертирования",
     "value_min": 1200.0, "value_max": 1280.0, "unit": "degC", "unit_normalized": "degC",
     "object": "температура конвертера", "geography": "world", "confidence": 0.83,
     "source_doc": "pub_gp2_2024",
     "quote": "Температура конвертирования штейна 1200-1280 С"},

    {"subject": "Файнштейн", "predicate": "содержание никеля",
     "value_min": 40.0, "value_max": 55.0, "unit": "wt%", "unit_normalized": "wt%",
     "object": "Ni в файнштейне", "geography": "RU", "confidence": 0.82,
     "source_doc": "pub_gp2_2024",
     "quote": "Содержание Ni в файнштейне 40-55 мас.%"},

    {"subject": "Файнштейн", "predicate": "содержание меди",
     "value_min": 20.0, "value_max": 35.0, "unit": "wt%", "unit_normalized": "wt%",
     "object": "Cu в файнштейне", "geography": "RU", "confidence": 0.80,
     "source_doc": "pub_gp2_2024",
     "quote": "Содержание Cu в файнштейне 20-35 мас.%"},

    # ── Эксперименты ──────────────────────────────────────────
    {"subject": "Эксперимент ЭЭ Ni", "predicate": "достигнутая чистота катода",
     "value_min": 99.9, "value_max": 99.99, "unit": "wt%", "unit_normalized": "wt%",
     "object": "чистота Ni катода", "geography": "RU", "confidence": 0.90,
     "source_doc": "pub_vostrikova",
     "quote": "В опытах Вострикова получен катод 99,9-99,99% Ni"},

    {"subject": "Эксперимент ЭЭ Ni", "predicate": "оптимальная плотность тока",
     "value_min": 230.0, "value_max": 270.0, "unit": "A/m2", "unit_normalized": "A/m2",
     "object": "оптимум ЭЭ", "geography": "RU", "confidence": 0.88,
     "source_doc": "pub_vostrikova",
     "quote": "Оптимум плотности тока в опытах: 230-270 А/м2"},

    {"subject": "Эксперимент POX Ni", "predicate": "извлечение Ni с H2O2",
     "value_min": 97.5, "value_max": 99.2, "unit": "%", "unit_normalized": "%",
     "object": "усиленный POX с оксидантом", "geography": "RU", "confidence": 0.87,
     "source_doc": "pub_gp2_2024",
     "quote": "Добавка H2O2 повышает извлечение Ni до 97,5-99,2%"},

    {"subject": "Эксперимент РО обессол.", "predicate": "давление подачи",
     "value_min": 2.5, "value_max": 4.5, "unit": "MPa", "unit_normalized": "MPa",
     "object": "оптимум давления RO", "geography": "RU", "confidence": 0.82,
     "source_doc": "pub_water_2023",
     "quote": "Оптимальное давление RO в пилоте 2,5-4,5 МПа"},

    {"subject": "Эксперимент флотация", "predicate": "извлечение Ni новый участок",
     "value_min": 87.0, "value_max": 91.0, "unit": "%", "unit_normalized": "%",
     "object": "новый участок Комсомольского", "geography": "RU", "confidence": 0.84,
     "source_doc": "pub_flotation",
     "quote": "На новом участке достигнуто извлечение Ni 87-91%"},

    {"subject": "Эксперимент МПГ-штейн", "predicate": "распределение Pd в штейн",
     "value_min": 88.0, "value_max": 93.0, "unit": "%", "unit_normalized": "%",
     "object": "Pd в штейне при ПВП", "geography": "RU", "confidence": 0.85,
     "source_doc": "pub_gp2_2024",
     "quote": "88-93% палладия переходит в штейн при взвешенной плавке"},

    {"subject": "Эксперимент SX Кобальт", "predicate": "степень экстракции Co",
     "value_min": 92.0, "value_max": 97.0, "unit": "%", "unit_normalized": "%",
     "object": "Co из Ni-электролита", "geography": "RU", "confidence": 0.83,
     "source_doc": "pub_gp2_2024",
     "quote": "Жидкостная экстракция Co: 92-97%"},

    {"subject": "Эксперимент нейтрализация", "predicate": "расход извести",
     "value_min": 2.5, "value_max": 5.0, "unit": "kg/t", "unit_normalized": "kg/t",
     "object": "CaO на нейтрализацию", "geography": "RU", "confidence": 0.78,
     "source_doc": "pub_water_2023",
     "quote": "Расход извести 2,5-5,0 кг/т стоков при нейтрализации"},

    # ── COMPARISON facts (РФ vs мир) ──────────────────────────
    {"subject": "Электроэкстракция", "predicate": "СРАВНЕНИЕ: энергопотребление РФ vs мир",
     "value_min": None, "value_max": None,
     "object": "РФ: 2400-3100 кВт·ч/т; Мир: 2200-2800 кВт·ч/т — разрыв до 10-15% в пользу лучших практик",
     "unit": None, "unit_normalized": None,
     "geography": "RU", "confidence": 0.82,
     "source_doc": "pub_gp1_2024",
     "quote": "Сравнение: РФ уступает мировым лидерам по энергоэффективности ЭЭ"},

    {"subject": "Автоклавное выщелачивание", "predicate": "СРАВНЕНИЕ: извлечение Ni РФ vs мир",
     "value_min": None, "value_max": None,
     "object": "РФ: 96-98%; Мир: 96-99% — практически паритет по лучшим проектам",
     "unit": None, "unit_normalized": None,
     "geography": "RU", "confidence": 0.84,
     "source_doc": "pub_pox_review",
     "quote": "Российские результаты POX сопоставимы с мировыми"},

    {"subject": "Флотация", "predicate": "СРАВНЕНИЕ: извлечение Ni РФ vs Финляндия",
     "value_min": None, "value_max": None,
     "object": "РФ: 85-92%; Финляндия Boliden: 88-94% — преимущество зарубежных флотаций",
     "unit": None, "unit_normalized": None,
     "geography": "world", "confidence": 0.78,
     "source_doc": "pub_flotation",
     "quote": "Boliden достигает 88-94% извлечения Ni благодаря тонкому помолу"},

    # ── CONTRADICTION facts ───────────────────────────────────
    {"subject": "Автоклавное выщелачивание", "predicate": "ПРОТИВОРЕЧИЕ: оптимальная температура",
     "value_min": None, "value_max": None,
     "object": "Источник А (Кузнецов): 230 С — оптимум; Источник Б (обзор POX): 245 С — выше извлечение",
     "unit": None, "unit_normalized": None,
     "geography": "RU", "confidence": 0.65,
     "source_doc": "pub_pox_review",
     "quote": "Два исследования дают разные оптимумы: 230 и 245 С — требуется верификация"},

    {"subject": "Флотация", "predicate": "ПРОТИВОРЕЧИЕ: крупность помола",
     "value_min": None, "value_max": None,
     "object": "Доклад Морозова: 65% кл. -0,074 мм достаточно; ГП №2-2024: оптимум 78-80%",
     "unit": None, "unit_normalized": None,
     "geography": "RU", "confidence": 0.60,
     "source_doc": "pub_flotation",
     "quote": "Противоречивые данные по крупности помола: 65% vs 78-80%"},

    # ── Производство Норникеля ────────────────────────────────
    {"subject": "Норникель", "predicate": "производство никеля 2023",
     "value_min": 194.0, "value_max": 209.0, "unit": "kt/year", "unit_normalized": "kt/year",
     "object": "никель товарный 2023", "geography": "RU", "confidence": 0.92,
     "source_doc": "pub_ecology_2024",
     "quote": "Производство товарного Ni Норникеля в 2023 г.: 194-209 тыс. т"},

    {"subject": "Норникель", "predicate": "производство палладия 2023",
     "value_min": 2.6, "value_max": 2.8, "unit": "t", "unit_normalized": "t",
     "object": "Pd товарный 2023", "geography": "RU",
     "confidence": 0.90, "source_doc": "pub_ecology_2024",
     "quote": "Норникель — мировой лидер по производству Pd: 2,6-2,8 Moz/год"},

    {"subject": "Кольская ГМК", "predicate": "производство никеля 2023",
     "value_min": 55.0, "value_max": 65.0, "unit": "kt/year", "unit_normalized": "kt/year",
     "object": "Ni товарный Кольская ГМК", "geography": "RU", "confidence": 0.85,
     "source_doc": "pub_ecology_2024",
     "quote": "Кольская ГМК производит 55-65 тыс. т/год товарного Ni"},

    # ── Прочие ────────────────────────────────────────────────
    {"subject": "Жидкостная экстракция", "predicate": "число ступеней SX",
     "value_min": 4.0, "value_max": 8.0, "unit": None, "unit_normalized": None,
     "object": "ступени экстракции SX", "geography": "world", "confidence": 0.78,
     "source_doc": "pub_gp2_2024",
     "quote": "Число ступеней SX при экстракции Ni/Co — 4-8"},

    {"subject": "Жидкостная экстракция", "predicate": "pH при экстракции Co",
     "value_min": 5.0, "value_max": 6.5, "unit": "pH", "unit_normalized": "pH",
     "object": "pH оптимум Co SX", "geography": "world", "confidence": 0.80,
     "source_doc": "pub_gp2_2024",
     "quote": "Оптимум pH для SX кобальта: 5,0-6,5"},

    {"subject": "Нейтрализация", "predicate": "pH стоков на выходе",
     "value_min": 6.5, "value_max": 9.0, "unit": "pH", "unit_normalized": "pH",
     "object": "требование к нейтрализованному стоку", "geography": "RU",
     "confidence": 0.88, "source_doc": "pub_water_2023",
     "quote": "pH сбрасываемых стоков должен быть 6,5-9,0 по нормативу"},

    {"subject": "Нейтрализация", "predicate": "остаточное содержание Ni",
     "value_min": None, "value_max": 0.1, "unit": "mg/L", "unit_normalized": "mg/L",
     "object": "ПДК Ni в сбросе", "geography": "RU", "confidence": 0.90,
     "source_doc": "pub_water_2023",
     "quote": "ПДК Ni для рыбохозяйственных водоёмов <= 0,1 мг/л"},

    {"subject": "Нейтрализация", "predicate": "остаточное содержание Cu",
     "value_min": None, "value_max": 0.01, "unit": "mg/L", "unit_normalized": "mg/L",
     "object": "ПДК Cu в сбросе", "geography": "RU", "confidence": 0.90,
     "source_doc": "pub_water_2023",
     "quote": "ПДК Cu для рыбохозяйственных водоёмов <= 0,01 мг/л"},

    {"subject": "Концентрат", "predicate": "содержание серы",
     "value_min": 25.0, "value_max": 35.0, "unit": "wt%", "unit_normalized": "wt%",
     "object": "S в флотоконцентрате", "geography": "RU", "confidence": 0.82,
     "source_doc": "pub_gp2_2024",
     "quote": "Содержание серы в флотоконцентрате Норникеля 25-35 мас.%"},

    {"subject": "Хвосты", "predicate": "содержание Ni потери",
     "value_min": 0.05, "value_max": 0.15, "unit": "wt%", "unit_normalized": "wt%",
     "object": "Ni в хвостах флотации", "geography": "RU", "confidence": 0.78,
     "source_doc": "pub_flotation",
     "quote": "Содержание Ni в хвостах: 0,05-0,15% — ориентир по потерям"},

    {"subject": "Автоклав", "predicate": "объём промышленный",
     "value_min": 100.0, "value_max": 500.0, "unit": "m3", "unit_normalized": "m3",
     "object": "объём промышленного автоклава", "geography": "world", "confidence": 0.75,
     "source_doc": "pub_pox_review",
     "quote": "Объём промышленных автоклавов POX: 100-500 м3"},

    {"subject": "Диафрагменная ячейка", "predicate": "ресурс мембраны",
     "value_min": 12.0, "value_max": 36.0, "unit": "month", "unit_normalized": "month",
     "object": "срок службы ионообменной мембраны", "geography": "world", "confidence": 0.70,
     "source_doc": "pub_vostrikova",
     "quote": "Ресурс катионообменной мембраны диафрагменной ячейки 12-36 месяцев"},

    {"subject": "Гипроникель", "predicate": "год основания",
     "value_min": 1929.0, "value_max": 1929.0, "unit": None, "unit_normalized": None,
     "object": "основан в 1929 г.", "geography": "RU", "confidence": 0.95,
     "source_doc": "pub_gp1_2024",
     "quote": "Институт Гипроникель основан в 1929 году"},
]


# ─────────────────────────────────────────────────────────────────────────────
# RELATIONS
# ─────────────────────────────────────────────────────────────────────────────

RELATIONS: list[tuple[str, str]] = [
    ("выщелачивание", "серная кислота"),
    ("выщелачивание", "никель"),
    ("автоклавное выщелачивание", "никель"),
    ("автоклавное выщелачивание", "кобальт"),
    ("автоклавное выщелачивание", "пероксид водорода"),
    ("электроэкстракция", "никель"),
    ("электроэкстракция", "медь"),
    ("электроэкстракция", "католит"),
    ("электроэкстракция", "анолит"),
    ("электроэкстракция", "электролит"),
    ("электролиз", "никель"),
    ("флотация", "концентрат"),
    ("флотация", "хвосты"),
    ("флотация", "флотореагент"),
    ("взвешенная плавка", "штейн"),
    ("взвешенная плавка", "шлак"),
    ("взвешенная плавка", "диоксид серы"),
    ("конвертирование", "штейн"),
    ("конвертирование", "файнштейн"),
    ("конвертирование", "конвертерный шлак"),
    ("обессоливание", "обратный осмос"),
    ("обессоливание", "ионный обмен"),
    ("обессоливание", "электродиализ"),
    ("нейтрализация", "известь"),
    ("нейтрализация", "гипс"),
    ("жидкостная экстракция", "кобальт"),
    ("конверсия со2", "диоксид серы"),
    ("конверсия со2", "серная кислота"),
    ("штейн", "мпг"),
    ("мпг", "палладий"),
    ("мпг", "платина"),
    ("мпг", "родий"),
    ("мпг", "рутений"),
    ("файнштейн", "никель"),
    ("файнштейн", "медь"),
    ("концентрат", "штейн"),
    ("сульфаты", "обессоливание"),
    ("хлориды", "обессоливание"),
    ("электроэкстракция", "ванна электроэкстракции"),
    ("электроэкстракция", "диафрагменная ячейка"),
    ("взвешенная плавка", "печь взвешенной плавки"),
    ("конвертирование", "конвертер"),
    ("автоклавное выщелачивание", "автоклав"),
    ("обратный осмос", "мембранный модуль"),
    ("фильтрация", "фильтр-пресс"),
    ("ионный обмен", "ионообменная колонна"),
    ("взвешенная плавка", "система очистки газов"),
    ("норникель", "надежда"),
    ("норникель", "медный завод"),
    ("норникель", "кольская гмк"),
    ("норникель", "комсомольский"),
    ("надежда", "электроэкстракция"),
    ("медный завод", "конвертирование"),
    ("гипроникель", "норникель"),
    ("востриков", "pub_vostrikova"),
    ("кузнецов", "pub_pox_review"),
    ("иванов", "pub_water_2023"),
    ("морозов", "pub_flotation"),
    ("петров", "pub_gp2_2024"),
    ("сидорова", "pub_ecology_2024"),
    ("pub_vostrikova", "exp_ew_ni"),
    ("pub_pox_review", "exp_pox_ni"),
    ("pub_water_2023", "exp_ro_desalt"),
    ("pub_flotation", "exp_flotation"),
    ("pub_gp2_2024", "exp_pgm_dist"),
]

DOCUMENTS: list[dict] = [
    {"id": "demo-1", "name": "Доклад_Вострикова_Н.М.pdf",       "size": 1596112,  "status": "completed", "chunks_total": 12, "chunks_done": 12, "chunks": 12},
    {"id": "demo-2", "name": "ГП_№1-2024.pdf",                  "size": 29323490, "status": "completed", "chunks_total": 24, "chunks_done": 24, "chunks": 24},
    {"id": "demo-3", "name": "ГП_№2-2024.pdf",                  "size": 21918599, "status": "completed", "chunks_total": 20, "chunks_done": 20, "chunks": 20},
    {"id": "demo-4", "name": "Обзор_POX_2022.pdf",              "size": 5124312,  "status": "completed", "chunks_total": 16, "chunks_done": 16, "chunks": 16},
    {"id": "demo-5", "name": "Водоподготовка_2023.pdf",         "size": 3870205,  "status": "completed", "chunks_total": 14, "chunks_done": 14, "chunks": 14},
    {"id": "demo-6", "name": "Флотация_2021.pdf",               "size": 4432801,  "status": "completed", "chunks_total": 10, "chunks_done": 10, "chunks": 10},
    {"id": "demo-7", "name": "Экологический_отчёт_2024.pdf",    "size": 8740112,  "status": "completed", "chunks_total": 18, "chunks_done": 18, "chunks": 18},
]

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

_STOPWORDS: set[str] = {
    "и", "в", "на", "с", "по", "для", "из", "как", "что", "это", "при",
    "или", "не", "к", "о", "об", "от", "до", "за", "же", "ли", "бы", "то",
    "у", "а", "какой", "какая", "какие", "каких", "чем", "где", "когда",
    "почему", "сколько", "можно", "нужно", "есть", "будет", "был", "была", "были",
}

_SYNONYMS: dict[str, str] = {
    "electrowinning": "электроэкстракция",
    "electroextraction": "электроэкстракция",
    "ew": "электроэкстракция",
    "пвп": "взвешенная плавка",
    "flash": "взвешенная плавка",
    "smelting": "взвешенная плавка",
    "pox": "автоклавное выщелачивание",
    "ro": "обратный осмос",
    "sx": "жидкостная экстракция",
    "matte": "штейн",
    "slag": "шлак",
    "pgm": "мпг",
    "pgms": "мпг",
    "ni": "никель",
    "cu": "медь",
    "co": "кобальт",
    "pd": "палладий",
    "pt": "платина",
    "rh": "родий",
    "h2so4": "серная кислота",
    "nickel": "никель",
    "copper": "медь",
    "cobalt": "кобальт",
    "palladium": "палладий",
    "platinum": "платина",
    "flotation": "флотация",
    "leaching": "выщелачивание",
    "desalination": "обессоливание",
    "водоподготовка": "обессоливание",
    "so2": "диоксид серы",
    "сульфат": "сульфаты",
    "sulfate": "сульфаты",
    "chloride": "хлориды",
    "хлорид": "хлориды",
    "extraction": "электроэкстракция",
    "electrolysis": "электролиз",
    "concentrate": "концентрат",
    "tailings": "хвосты",
    "converter": "конвертер",
}


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[\wа-яё\-]{2,}", text.lower())
    result: list[str] = []
    for w in words:
        if w in _STOPWORDS:
            continue
        w = _SYNONYMS.get(w, w)
        if w not in result:
            result.append(w)
    return result


def _token_overlap_score(query_tokens: list[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    text_lower = text.lower()
    hits = sum(1 for t in query_tokens if t in text_lower)
    return hits / len(query_tokens)


def _score_entity(query_tokens: list[str], entity: dict) -> float:
    text = (entity.get("name") or "") + " " + (entity.get("description") or "")
    return _token_overlap_score(query_tokens, text)


def _score_fact(query_tokens: list[str], fact: dict) -> float:
    text = (
        (fact.get("subject") or "")
        + " " + (fact.get("predicate") or "")
        + " " + (fact.get("object") or "")
    )
    return _token_overlap_score(query_tokens, text)


def _format_value(fact: dict) -> str:
    vmin, vmax = fact.get("value_min"), fact.get("value_max")
    unit = fact.get("unit_normalized") or fact.get("unit") or ""
    if vmin is not None and vmax is not None:
        val = f"{vmin:g}" if vmin == vmax else f"{vmin:g}-{vmax:g}"
        return f"{val} {unit}".strip()
    elif vmax is not None:
        return f"<={vmax:g} {unit}".strip()
    elif vmin is not None:
        return f">={vmin:g} {unit}".strip()
    return fact.get("object", "нет данных")


def _related_entity_keys(seed_keys: set[str]) -> set[str]:
    neighbours: set[str] = set()
    for s, t in RELATIONS:
        if s in seed_keys:
            neighbours.add(t)
        if t in seed_keys:
            neighbours.add(s)
    return neighbours


_PUB_TO_DOC: dict[str, str] = {
    "pub_gp1_2024":    "ГП_№1-2024.pdf",
    "pub_gp2_2024":    "ГП_№2-2024.pdf",
    "pub_vostrikova":  "Доклад_Вострикова_Н.М.pdf",
    "pub_pox_review":  "Обзор_POX_2022.pdf",
    "pub_water_2023":  "Водоподготовка_2023.pdf",
    "pub_flotation":   "Флотация_2021.pdf",
    "pub_ecology_2024":"Экологический_отчёт_2024.pdf",
}


def _doc_name_for_key(source_key: str | None) -> str | None:
    if not source_key:
        return None
    return _PUB_TO_DOC.get(source_key)


# ─────────────────────────────────────────────────────────────────────────────
# GRAPHRAG CONTEXT BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def get_rag_context(question: str, region: str | None = None) -> dict:
    """Full GraphRAG context: 2-hop entity expansion + fact scoring."""
    tokens = _tokenize(question)

    # Stage 1: Seed entities
    scored_entities: list[tuple[float, dict]] = []
    for e in ENTITIES:
        s = _score_entity(tokens, e)
        if s > 0:
            scored_entities.append((s, e))
    scored_entities.sort(key=lambda x: -x[0])
    seed_entities = [e for _, e in scored_entities[:10]]
    seed_keys = {e["key"] for e in seed_entities}

    # Stage 2: 2-hop expansion
    hop1_keys = _related_entity_keys(seed_keys)
    hop2_keys = _related_entity_keys(hop1_keys) - seed_keys - hop1_keys
    all_keys = seed_keys | hop1_keys | hop2_keys

    expanded: list[dict] = []
    seen_keys: set[str] = set()
    for e in ENTITIES:
        if e["key"] in all_keys and e["key"] not in seen_keys:
            seen_keys.add(e["key"])
            expanded.append(e)

    # Stage 3: Score facts
    all_entity_names = {e["name"].lower() for e in expanded}
    scored_facts: list[tuple[float, dict]] = []
    for f in FACTS:
        subj_match = float(f["subject"].lower() in all_entity_names)
        token_score = _score_fact(tokens, f)
        combined = 0.6 * subj_match + 0.4 * token_score
        if combined <= 0:
            continue
        if region and region.lower() not in ("all", ""):
            geo = (f.get("geography") or "").lower()
            if geo and geo != "unknown" and region.lower() not in geo and geo not in region.lower():
                combined *= 0.3
        scored_facts.append((combined, f))
    scored_facts.sort(key=lambda x: (-x[0], -(x[1].get("confidence") or 0.5)))
    top_facts = [f for _, f in scored_facts[:40]]

    # Stage 4: Collect sources
    source_docs: list[str] = []
    seen_docs: set[str] = set()
    for f in top_facts:
        doc = _doc_name_for_key(f.get("source_doc"))
        if doc and doc not in seen_docs:
            seen_docs.add(doc)
            source_docs.append(doc)

    return {
        "entities": expanded[:25],
        "facts": top_facts,
        "sources": source_docs,
        "seed_count": len(seed_entities),
        "hop1_count": len(hop1_keys),
        "hop2_count": len(hop2_keys),
        "total_entities": len(expanded),
    }


# ─────────────────────────────────────────────────────────────────────────────
# GRAPHRAG ASK
# ─────────────────────────────────────────────────────────────────────────────

def ask(question: str, region: str | None = None) -> dict:
    """GraphRAG + CAG ask in demo mode.

    Returns: {answer, sources, facts, cached, mode, retrieval_stats}
    """
    # CAG check
    cached = _cache_get(question)
    if cached:
        return {**cached, "cached": True, "mode": "cache"}

    ctx = get_rag_context(question, region)
    entities  = ctx["entities"]
    top_facts = ctx["facts"]
    sources   = ctx["sources"]

    if not top_facts and not entities:
        result = {
            "answer": (
                "В базе знаний нет данных по данному запросу. "
                "Загрузите документы через вкладку «Документы» для пополнения графа знаний."
            ),
            "sources": [], "facts": [], "cached": False,
            "mode": "graph_rag",
            "retrieval_stats": {
                "entities_found": 0, "facts_found": 0, "chunks_found": 0,
                "hops": 0, "cache_hit": False,
            },
        }
        return result

    # Build structured answer
    parts: list[str] = []

    entity_names = list(dict.fromkeys(e["name"] for e in entities[:6]))
    parts.append(
        f"По запросу **«{question.strip()}»** граф знаний нашёл "
        f"{len(top_facts)} фактов по {len(entities)} сущностям (2-hop traversal)."
    )

    if entity_names:
        parts.append(f"\n**Ключевые сущности:** {', '.join(entity_names)}.")

    # Grouped facts
    subj_groups: dict[str, list[dict]] = {}
    for f in top_facts[:25]:
        subj_groups.setdefault(f["subject"], []).append(f)

    fact_lines: list[str] = []
    n = 1
    for subj, facts in list(subj_groups.items())[:10]:
        for f in facts[:4]:
            val = _format_value(f)
            geo = f.get("geography") or "unknown"
            conf = f.get("confidence") or 0.5
            fact_lines.append(
                f"{n}. **{subj}** — {f['predicate']}: **{val}** "
                f"[гео: {geo}, достоверность: {conf:.0%}]"
            )
            n += 1
    if fact_lines:
        parts.append("\n**Факты из графа знаний:**\n" + "\n".join(fact_lines))

    # Comparison facts
    comp_facts = [f for f in top_facts if "СРАВНЕНИЕ" in f.get("predicate", "")]
    if comp_facts:
        comp_lines = [f"- {f['predicate']}: {f['object']}" for f in comp_facts[:3]]
        parts.append("\n**Сравнительный анализ (РФ vs мировая практика):**\n" + "\n".join(comp_lines))

    # Contradiction facts
    contra_facts = [f for f in top_facts if "ПРОТИВОРЕЧИЕ" in f.get("predicate", "")]
    if contra_facts:
        contra_lines = [f"! {f['predicate']}: {f['object']}" for f in contra_facts[:2]]
        parts.append("\n**Выявленные противоречия в источниках:**\n" + "\n".join(contra_lines))

    if sources:
        parts.append(f"\n**Источники:** {', '.join(sources[:5])}")

    answer = "\n".join(parts)

    facts_out = [
        {
            "subject": f["subject"],
            "predicate": f["predicate"],
            "value": _format_value(f),
            "geography": f.get("geography", "unknown"),
            "confidence": f.get("confidence", 0.5),
        }
        for f in top_facts[:15]
    ]

    result = {
        "answer": answer,
        "sources": sources,
        "facts": facts_out,
        "cached": False,
        "mode": "graph_rag",
        "retrieval_stats": {
            "entities_found": len(entities),
            "facts_found": len(top_facts),
            "chunks_found": 0,
            "hops": 2,
            "cache_hit": False,
        },
    }

    _cache_put(question, result)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# COMPARISON
# ─────────────────────────────────────────────────────────────────────────────

def get_comparison(topic_a: str, topic_b: str) -> dict:
    from comparison import build_comparison
    def resolve(value: str) -> dict:
        entity = next((e for e in ENTITIES if e["key"] == value or e["name"].casefold() == value.casefold()), None)
        if not entity:
            raise ValueError(f"Сущность не найдена: {value}")
        return {"key": entity["key"], "name": entity["name"], "type": entity["type"]}
    a, b = resolve(topic_a), resolve(topic_b)
    facts_a = [fact for fact in FACTS if fact["subject"] == a["name"]]
    facts_b = [fact for fact in FACTS if fact["subject"] == b["name"]]
    return build_comparison(a, facts_a, b, facts_b)


def suggest_entities(query: str, limit: int = 8) -> list[dict]:
    needle = query.strip().casefold()
    counts: dict[str, int] = {}
    for fact in FACTS:
        counts[fact["subject"]] = counts.get(fact["subject"], 0) + 1
    found = [e for e in ENTITIES if counts.get(e["name"], 0) and (not needle or needle in e["name"].casefold())]
    found.sort(key=lambda e: (not e["name"].casefold().startswith(needle), e["name"]))
    return [{"key": e["key"], "name": e["name"], "type": e["type"], "fact_count": counts[e["name"]]} for e in found[:limit]]


# ─────────────────────────────────────────────────────────────────────────────
# KNOWLEDGE GAPS
# ─────────────────────────────────────────────────────────────────────────────

def get_knowledge_gaps() -> dict:
    """Entities with few facts or low average confidence."""
    from collections import Counter
    subj_counts: Counter = Counter()
    subj_conf: dict[str, float] = {}
    for f in FACTS:
        s = f["subject"]
        subj_counts[s] += 1
        subj_conf[s] = subj_conf.get(s, 0.0) + (f.get("confidence") or 0.5)

    entity_names = {e["name"] for e in ENTITIES}
    gaps: list[dict] = []
    for name in entity_names:
        count = subj_counts.get(name, 0)
        avg_conf = subj_conf.get(name, 0.0) / max(count, 1)
        if count < 2 or avg_conf < 0.75:
            gaps.append({
                "topic": name,
                "description": f"Мало фактов о сущности ({count} ед.)" if count < 2 else f"Низкая достоверность фактов (avg: {round(avg_conf, 2)})",
                "severity": "high" if count == 0 else "medium",
            })
    gaps.sort(key=lambda x: x["severity"] == "high", reverse=True)
    return {
        "gaps": gaps[:20],
        "total_gaps": len(gaps),
        "coverage": round(1 - len(gaps) / max(len(entity_names), 1), 2),
    }


# ─────────────────────────────────────────────────────────────────────────────
# PARAMETRIC FACT SEARCH
# ─────────────────────────────────────────────────────────────────────────────

def search_facts(
    query: str,
    geography: str | None = None,
    min_confidence: float = 0.0,
    value_min: float | None = None,
    value_max_param: float | None = None,
    unit: str | None = None,
) -> list[dict]:
    """Full parametric fact search."""
    tokens = _tokenize(query) if query else []
    results: list[dict] = []
    for f in FACTS:
        score = _score_fact(tokens, f) if tokens else 1.0
        if tokens and score <= 0:
            continue

        if geography and geography.lower() not in ("all", ""):
            geo = (f.get("geography") or "").lower()
            if geo and geo != "unknown" and geography.lower() not in geo:
                continue

        if (f.get("confidence") or 0.0) < min_confidence:
            continue

        if value_min is not None:
            fv = f.get("value_min") or f.get("value_max")
            if fv is None or fv < value_min:
                continue
        if value_max_param is not None:
            fv = f.get("value_max") or f.get("value_min")
            if fv is None or fv > value_max_param:
                continue

        if unit:
            fu = (f.get("unit_normalized") or f.get("unit") or "").lower()
            if unit.lower() not in fu and fu not in unit.lower():
                continue

        results.append({**f, "_score": round(score, 3)})

    results.sort(key=lambda x: (-x["_score"], -(x.get("confidence") or 0.0)))
    return results[:30]


# ─────────────────────────────────────────────────────────────────────────────
# ENTITY RELATIONS (2-hop paths)
# ─────────────────────────────────────────────────────────────────────────────

def get_entity_relations(key: str) -> dict:
    """2-hop relation paths from an entity."""
    hop1: list[dict] = []
    hop2: list[dict] = []
    seen_hop1: set[str] = set()

    for s, t in RELATIONS:
        if s == key and t not in seen_hop1:
            hop1.append({"from": s, "to": t, "hop": 1})
            seen_hop1.add(t)
            for s2, t2 in RELATIONS:
                if s2 == t and t2 != key:
                    hop2.append({"from": t, "to": t2, "hop": 2})
        elif t == key and s not in seen_hop1:
            hop1.append({"from": t, "to": s, "hop": 1})
            seen_hop1.add(s)
            for s2, t2 in RELATIONS:
                if s2 == s and t2 != key:
                    hop2.append({"from": s, "to": t2, "hop": 2})

    return {
        "entity_key": key,
        "hop1": hop1[:20],
        "hop2": hop2[:20],
        "total_paths": len(hop1) + len(hop2),
    }


# ─────────────────────────────────────────────────────────────────────────────
# SUBGRAPH
# ─────────────────────────────────────────────────────────────────────────────

def get_subgraph(
    search: str | None = None,
    etypes: list[str] | None = None,
    limit: int = 150,
    region: str | None = None,
    min_confidence: float | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    month_from: int | None = None,
    month_to: int | None = None,
) -> dict:
    entities = ENTITIES
    if search:
        tokens = _tokenize(search)
        entities = [e for e in entities if _score_entity(tokens, e) > 0]
    if etypes:
        entities = [e for e in entities if e["type"] in etypes]
    if any(v is not None for v in (region, min_confidence, year_from, year_to, month_from, month_to)):
        entities = [
            e for e in entities
            if _entity_matches_graph_filters(
                e,
                region=region,
                min_confidence=min_confidence,
                year_from=year_from,
                year_to=year_to,
                month_from=month_from,
                month_to=month_to,
            )
        ]

    keys = {e["key"] for e in entities[:limit]}
    links = [
        {"source": s, "target": t, "label": "RELATED"}
        for s, t in RELATIONS
        if s in keys and t in keys
    ]
    nodes = [
        {"key": e["key"], "name": e["name"], "type": e["type"], "description": e["description"]}
        for e in entities[:limit]
    ]
    return {"nodes": nodes, "links": links}


def _extract_years_from_fact(fact: dict) -> list[int]:
    text = " ".join(
        str(fact.get(field, "") or "")
        for field in ("predicate", "object", "quote", "source_doc")
    )
    return [int(match) for match in re.findall(r"\b(?:19|20)\d{2}\b", text)]


def _fact_matches_period(
    fact: dict,
    year_from: int | None = None,
    year_to: int | None = None,
    month_from: int | None = None,
    month_to: int | None = None,
) -> bool:
    if year_from is not None or year_to is not None:
        years = _extract_years_from_fact(fact)
        if not years:
            return False
        if year_from is not None and all(year < year_from for year in years):
            return False
        if year_to is not None and all(year > year_to for year in years):
            return False

    if month_from is not None or month_to is not None:
        if fact.get("unit_normalized") != "month":
            return False
        values = [v for v in (fact.get("value_min"), fact.get("value_max")) if isinstance(v, (int, float))]
        if not values:
            return False
        low = min(values)
        high = max(values)
        if month_from is not None and high < month_from:
            return False
        if month_to is not None and low > month_to:
            return False

    return True


def _entity_matches_graph_filters(
    entity: dict,
    region: str | None = None,
    min_confidence: float | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    month_from: int | None = None,
    month_to: int | None = None,
) -> bool:
    facts = [f for f in FACTS if f["subject"] == entity["name"]]
    if not facts:
        return False

    year_start = min(year_from, year_to) if year_from is not None and year_to is not None else year_from
    year_end = max(year_from, year_to) if year_from is not None and year_to is not None else year_to
    month_start = min(month_from, month_to) if month_from is not None and month_to is not None else month_from
    month_end = max(month_from, month_to) if month_from is not None and month_to is not None else month_to

    for fact in facts:
        if region and region.lower() not in ("all", "any", ""):
            geography = (fact.get("geography") or "").lower()
            normalized_region = region.lower()
            if normalized_region == "domestic":
                normalized_region = "ru"
            elif normalized_region in ("foreign", "world_excl_ru"):
                normalized_region = "world"
            if geography != normalized_region:
                continue
        if min_confidence is not None and (fact.get("confidence") or 0.0) < min_confidence:
            continue
        if not _fact_matches_period(
            fact,
            year_from=year_start,
            year_to=year_end,
            month_from=month_start,
            month_to=month_end,
        ):
            continue
        return True
    return False


def get_entity_details(key: str) -> dict | None:
    for e in ENTITIES:
        if e["key"] == key:
            efacts = [
                {
                    "predicate": f["predicate"],
                    "object": f.get("object", ""),
                    "value_min": f.get("value_min"),
                    "value_max": f.get("value_max"),
                    "unit": f.get("unit_normalized"),
                    "geography": f.get("geography", "unknown"),
                    "confidence": f.get("confidence", 0.5),
                    "quote": f.get("quote", ""),
                }
                for f in FACTS
                if f["subject"] == e["name"]
            ]
            return {
                "name": e["name"],
                "type": e["type"],
                "description": e["description"],
                "aliases": [],
                "facts": efacts,
                "documents": [d["name"] for d in DOCUMENTS[:3]],
            }
    return None


# ─────────────────────────────────────────────────────────────────────────────
# STUBS (called by production paths when DEMO=True)
# ─────────────────────────────────────────────────────────────────────────────

def run(*args: Any, **kwargs: Any) -> list:
    """Stub for health-check compatibility."""
    return [{"ok": 1}]


def init_schema() -> None:
    pass


def list_documents() -> list:
    return DOCUMENTS


def chunk_exists(_hash: str) -> bool:
    return False


def upsert_entity(*args: Any, **kwargs: Any) -> None:
    pass


def upsert_relation(*args: Any, **kwargs: Any) -> None:
    pass


def create_fact(*args: Any, **kwargs: Any) -> None:
    pass


def mark_chunk_processed(_hash: str) -> None:
    pass


def set_document_progress(*args: Any, **kwargs: Any) -> None:
    pass


def set_document_status(*args: Any, **kwargs: Any) -> None:
    pass


def upsert_document(*args: Any, **kwargs: Any) -> None:
    pass


def upsert_chunk(*args: Any, **kwargs: Any) -> None:
    pass


def invalidate_all() -> None:
    clear_cache()
