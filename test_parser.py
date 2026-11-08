"""Быстрая проверка парсера: запустите  python test_parser.py"""

from parser import parse_resume

text = parse_resume(pdf_file="test_data/resume_strong.pdf")
print("Длина текста:", len(text))
print("Первые 300 символов:")
print(text[:300])
