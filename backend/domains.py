"""Technological domains for the NORNIKEL Knowledge Map.

Domains classify knowledge by industrial area:
hydrometallurgy, pyrometallurgy, ecology, waste processing, etc.
Each entity and document can be tagged with one or more domains.
"""

from typing import Optional

# ── Built-in domains ────────────────────────────────────────────
# id → (label_ru, label_en, description)
BUILTIN_DOMAINS: dict[str, tuple[str, str, str]] = {
    "hydrometallurgy": (
        "Гидрометаллургия",
        "Hydrometallurgy",
        "Выщелачивание, электроэкстракция, обессоливание, флотация",
    ),
    "pyrometallurgy": (
        "Пирометаллургия",
        "Pyrometallurgy",
        "Взвешенная плавка, конвертирование, обжиг",
    ),
    "ecology": (
        "Экология",
        "Ecology",
        "Очистка газов, водоочистка, выбросы, отходящие газы",
    ),
    "waste_processing": (
        "Переработка отходов",
        "Waste Processing",
        "Хвосты, шлаки, техногенные материалы, вторичное сырьё",
    ),
    "mining": (
        "Добыча",
        "Mining",
        "Рудоподготовка, бурение, взрывные работы",
    ),
    "materials_science": (
        "Материаловедение",
        "Materials Science",
        "Свойства сплавов, коррозия, механические характеристики",
    ),
    "analytics": (
        "Аналитика",
        "Analytics",
        "Методы анализа, спектрометрия, химический контроль",
    ),
    "economics": (
        "Экономика",
        "Economics",
        "Себестоимость, капитальные затраты, ТЭО",
    ),
}

# ── Keywords for automatic domain classification ────────────────
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "hydrometallurgy": [
        "выщелачивание", "leaching", "электроэкстракция", "electrowinning",
        "флотация", "flotation", "обессоливание", "desalination",
        "водоподготовка", "автоклав", "autoclave", "кислотное выщелачивание",
        "аммиачное выщелачивание", "растворительное выщелачивание",
        "ионный обмен", "ion exchange", "осмос", "reverse osmosis",
        "цианирование", "цианид", "cyanide", "гидрометаллургическ",
        "седиментация", "осаждение", "экстракция",
    ],
    "pyrometallurgy": [
        "плавка", "smelting", "взвешенная плавка", "flash smelting",
        "конвертирование", "converting", "обжиг", "roasting",
        "печь", "furnace", "капсульная плавка", "reverberatory",
        "шахтная печь", "электропечь", "electric furnace",
        "конвертер", "converter", "отражательная печь",
        "ПВП", "POX", "плавильн",
    ],
    "ecology": [
        "экологи", "ecology", "выброс", "emission", "сброс", "discharge",
        "очистка газ", "gas cleaning", "газоочистк", "SO2", "SO₂",
        "пылеулавлив", "dust collect", "фильтрация газ",
        "водоочистк", "water treatment", "очистка сточных",
        "биологическ очистк", "хвостохранилищ", "tailings pond",
        "рекультивац", "remediation", "загрязнен", "pollution",
        "ПДК", "предельно допустим", "углеродный след", "ESG",
    ],
    "waste_processing": [
        "отход", "waste", "хвост", "tailings", "шлак", "slag",
        "шлам", "sludge", "вторичн", "secondary", "переработк",
        "recycling", "reprocessing", "техноген", "technogenic",
        "утилизац", "utilization", "захоронен", "disposal",
        "конвертерный шлак", "гипс техноген",
    ],
    "mining": [
        "добыч", "mining", "руд", "ore", "бурени", "drilling",
        "взрывн", "blasting", "карьер", "quarry", "шахт",
        "mine", "подземн", "underground", "открыт", "open pit",
        "разработк", "проходческ", "geolog", "геолог", "разведк",
    ],
    "materials_science": [
        "материал", "material", "сплав", "alloy", "микроструктур",
        "microstructure", "коррози", "corrosion", "механическ",
        "mechanical", "прочност", "strength", "твёрдост", "hardness",
        "термообработк", "heat treatment", "отжиг", "annealing",
        "закалк", "quenching", "никелев", "nickel alloy",
    ],
    "analytics": [
        "анализ", "analysis", "спектр", "spectr", "рентген",
        "X-ray", "микроскоп", "microscop", "титрован", "titrat",
        "химический анализ", "chemical analysis", "ICP",
        "атомно-абсорбц", "AAS", "гравиметри",
    ],
    "economics": [
        "экономик", "economics", "себестоимость", "cost",
        "капитальн", "capital", "ТЭО", "feasibility",
        "инвестиц", "investment", "рентабельн", "profitabil",
        "бюджет", "budget", "финансов", "financial",
        "затрат", "pricing", "unit cost",
    ],
}


def get_all_domains() -> list[dict]:
    """Return all available domains with labels."""
    return [
        {"id": k, "name_ru": v[0], "name_en": v[1], "description": v[2]}
        for k, v in BUILTIN_DOMAINS.items()
    ]


def get_domain_id(name: str) -> Optional[str]:
    """Resolve domain name (RU or EN) to its id."""
    low = name.strip().lower()
    for k, v in BUILTIN_DOMAINS.items():
        if k == low or v[0].lower() == low or v[1].lower() == low:
            return k
    return None


def validate_domains(domains: list[str] | None) -> list[str]:
    """Validate and normalize a list of domain names/ids."""
    if not domains:
        return []
    result = []
    for d in domains:
        did = get_domain_id(d)
        result.append(did or d.strip().lower().replace(" ", "_"))
    return list(dict.fromkeys(result))


def classify_text(text: str, min_matches: int = 1) -> list[str]:
    """Classify text into domains based on keyword matching.

    Returns domain ids sorted by match count (most relevant first).
    Empty list if fewer than min_matches keywords found.
    """
    if not text:
        return []

    text_lower = text.lower()
    scores: dict[str, int] = {}

    for domain_id, keywords in DOMAIN_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw.lower() in text_lower)
        if count >= min_matches:
            scores[domain_id] = count

    if not scores:
        return []

    return [d[0] for d in sorted(scores.items(), key=lambda x: x[1], reverse=True)]


def classify_entity(name: str, description: str = "", aliases: list[str] | None = None) -> list[str]:
    """Classify an entity into domains based on name, description, aliases."""
    parts = [name, description]
    if aliases:
        parts.extend(aliases)
    return classify_text(" ".join(parts))


def classify_document(text: str, max_domains: int = 3) -> list[str]:
    """Classify a document text chunk into domains. Returns top N."""
    return classify_text(text)[:max_domains]


def domain_label(domain_id: str) -> str:
    """Return Russian label for a domain id."""
    entry = BUILTIN_DOMAINS.get(domain_id)
    return entry[0] if entry else domain_id


def domain_label_en(domain_id: str) -> str:
    """Return English label for a domain id."""
    entry = BUILTIN_DOMAINS.get(domain_id)
    return entry[1] if entry else domain_id
