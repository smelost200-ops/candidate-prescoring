"""Извлечение и подготовка текста резюме из PDF (pdfplumber)."""

import re
import unicodedata

import pdfplumber

MAX_CHARS = 6000  # ограничение объёма текста для запроса к модели


def extract_pdf_text(pdf_file) -> str:
    """Возвращает весь текст PDF одной непрерывной строкой.

    pdf_file — путь к файлу или файловый объект (io.BytesIO из
    Streamlit file_uploader). Таблицы и оформление игнорируем:
    работаем только с содержимым.
    """
    if pdf_file is None:
        return ""
    with pdfplumber.open(pdf_file) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages)


def clean_text(text: str) -> str:
    """Чистит текст: невидимые символы, переносы, табуляции, лишние пробелы."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    text = text.replace("\t", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_CHARS]


def parse_resume(pdf_file=None, full_text: str = "") -> str:
    """Объединяет источники (PDF и/или текстовое поле) и возвращает чистый текст.

    Если текста нет ни в одном источнике — возвращает пустую строку.
    """
    parts = []
    pdf_text = extract_pdf_text(pdf_file)
    if pdf_text.strip():
        parts.append(pdf_text)
    if full_text and full_text.strip():
        parts.append(full_text)
    combined = " ".join(parts)
    return clean_text(combined)
