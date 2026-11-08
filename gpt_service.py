"""Запрос к LLM (OpenAI-совместимый API) и получение строгого JSON.

OpenAI заменён на ProxyAPI (OpenAI-совместимый): меняется только
base_url в .env, вся логика SDK остаётся без изменений.
"""

import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY", "")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.proxyapi.ru/v1")
MODEL = os.getenv("MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """Ты — опытный HR-аналитик. Оцени, насколько резюме кандидата соответствует вакансии.

Правила:
1. Оценивай только по тексту: не придумывай факты, которых нет в резюме.
2. Поставь три оценки по шкале 0-100:
   - hard_skills — совпадение технических навыков кандидата с требованиями вакансии;
   - experience — релевантность опыта кандидата (стаж, сфера проектов, уровень позиции);
   - soft_skills — совпадение мягких навыков (командная работа, коммуникация и т.п.).
3. Укажи сильные стороны (strengths), слабые стороны (weaknesses) и недостающие
   навыки (missing_skills) — списками коротких пунктов на русском языке.
4. В summary дай краткий вывод о соответствии (2-4 предложения).
5. Ответ — СТРОГО валидный JSON без markdown-блоков и пояснений, ровно по схеме:
{"hard_skills": 0, "experience": 0, "soft_skills": 0, "strengths": ["..."], "weaknesses": ["..."], "missing_skills": ["..."], "summary": "..."}"""

USER_TEMPLATE = """ВАКАНСИЯ:
{vacancy}

РЕЗЮМЕ КАНДИДАТА:
{resume}"""

# альтернативные названия полей, которые модель может вернуть вместо канонических
KEY_ALIASES = {
    "hard_skills": ("hard_skills", "hard", "hard_skills_score", "hardSkills"),
    "experience": ("experience", "exp", "experience_score", "work_experience"),
    "soft_skills": ("soft_skills", "soft", "soft_skills_score", "softSkills"),
    "strengths": ("strengths", "strong_sides", "strengths_list", "pros"),
    "weaknesses": ("weaknesses", "weak_sides", "weaknesses_list", "cons"),
    "missing_skills": ("missing_skills", "missing", "gaps", "missing_skills_list"),
    "summary": ("summary", "resume_summary", "conclusion", "verdict"),
}


def _client() -> OpenAI:
    if not API_KEY:
        raise RuntimeError(
            "Не задан OPENAI_API_KEY. Создайте файл .env по образцу .env.example."
        )
    return OpenAI(api_key=API_KEY, base_url=BASE_URL)


def repair_json(text: str):
    """Приводит ответ модели к валидному JSON.

    Последовательно пробуем: ответ как есть -> без markdown-блоков ->
    без лишних слэшей -> одинарные кавычки -> без висячих запятых ->
    без переносов строк -> вырезаем блок {...} и повторяем ремонт.
    """
    if not text or not text.strip():
        raise ValueError("Пустой ответ модели")
    raw = text.strip()

    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        pass

    cleaned = re.sub(r"^```[a-zA-Z]*", "", raw)
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    cleaned = cleaned.replace("\\", "")
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    if '"' not in cleaned and "'" in cleaned:
        quoted = cleaned.replace("'", '"')
        try:
            return json.loads(quoted)
        except (json.JSONDecodeError, ValueError):
            pass
        cleaned = quoted

    no_trailing_commas = re.sub(r",\s*([}\]])", r"\1", cleaned)
    if no_trailing_commas != cleaned:
        try:
            return json.loads(no_trailing_commas)
        except (json.JSONDecodeError, ValueError):
            pass
    cleaned = no_trailing_commas

    for candidate in (raw, cleaned):
        flat = candidate.replace("\r", " ").replace("\n", " ")
        try:
            return json.loads(flat)
        except (json.JSONDecodeError, ValueError):
            pass

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match and match.group(0) != raw:
        return repair_json(match.group(0))

    raise ValueError("Не удалось восстановить JSON из ответа модели")


def _pick(data: dict, key: str):
    for alias in KEY_ALIASES[key]:
        if alias in data:
            return data[alias]
    return None


def _to_int(value, default: int = 0) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def _to_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, dict):
        return [f"{k}: {v}" for k, v in value.items()]
    if isinstance(value, str):
        parts = re.split(r"\s*\|\s*|\s-\s|;", value)
        return [p.strip(" -•") for p in parts if p.strip()]
    return []


def normalize_analysis(data) -> dict:
    """Нормализует разобранный JSON: канонические ключи и типы полей."""
    if not isinstance(data, dict):
        raise ValueError("Ответ модели не является JSON-объектом")
    return {
        "hard_skills": _to_int(_pick(data, "hard_skills")),
        "experience": _to_int(_pick(data, "experience")),
        "soft_skills": _to_int(_pick(data, "soft_skills")),
        "strengths": _to_list(_pick(data, "strengths")),
        "weaknesses": _to_list(_pick(data, "weaknesses")),
        "missing_skills": _to_list(_pick(data, "missing_skills")),
        "summary": str(_pick(data, "summary") or "").strip(),
    }


def final_score(hard: int, experience: int, soft: int, weights=(0.6, 0.25, 0.15)) -> int:
    """Итоговый балл по взвешенной формуле (0-100). Веса нормализуются к 1."""
    total = float(sum(weights))
    if total <= 0:
        return 0
    w_hard, w_exp, w_soft = (w / total for w in weights)
    return int(round(hard * w_hard + experience * w_exp + soft * w_soft))


def analyze_candidate(vacancy_text: str, resume_text: str, model: str = None) -> dict:
    """Отправляет вакансию и резюме в модель, возвращает нормализованный dict."""
    response = _client().chat.completions.create(
        model=model or MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_TEMPLATE.format(
                    vacancy=vacancy_text.strip(), resume=resume_text.strip()
                ),
            },
        ],
        temperature=0.2,
    )
    raw = response.choices[0].message.content or ""
    data = repair_json(raw)
    return normalize_analysis(data)
