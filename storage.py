"""История оценок кандидатов (CSV-файл)."""

import json
import os
import uuid
from datetime import datetime

import pandas as pd

HISTORY_PATH = os.getenv("HISTORY_CSV", "candidates_history.csv")

COLUMNS = [
    "token", "name", "datetime", "model",
    "hard_skills", "experience", "soft_skills", "score",
    "weights", "strengths", "weaknesses", "missing_skills", "summary",
]


def load_history() -> pd.DataFrame:
    """Загружает историю; если файла нет или он пуст — возвращает пустую таблицу."""
    if not os.path.exists(HISTORY_PATH):
        return pd.DataFrame(columns=COLUMNS)
    try:
        df = pd.read_csv(HISTORY_PATH, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=COLUMNS)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[COLUMNS]


def append_record(name, model, hard, experience, soft, score, weights, analysis) -> dict:
    """Добавляет нового кандидата в историю и возвращает его запись."""
    record = {
        "token": uuid.uuid4().hex[:8],
        "name": (name or "Без имени").strip(),
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": model,
        "hard_skills": hard,
        "experience": experience,
        "soft_skills": soft,
        "score": score,
        "weights": weights,
        "strengths": " | ".join(analysis.get("strengths", [])),
        "weaknesses": " | ".join(analysis.get("weaknesses", [])),
        "missing_skills": " | ".join(analysis.get("missing_skills", [])),
        "summary": analysis.get("summary", ""),
    }
    df = load_history()
    df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
    df.to_csv(HISTORY_PATH, index=False, encoding="utf-8-sig")
    return record


def candidate_json(record: dict) -> str:
    """Сериализует запись кандидата в красивый JSON для скачивания."""
    return json.dumps(record, ensure_ascii=False, indent=2)
