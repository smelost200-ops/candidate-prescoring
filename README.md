# Прескоринг кандидатов на вакансии (ИИ-ассистент)

Веб-сервис предварительной оценки кандидатов: загрузите текст вакансии и
PDF-резюме — сервис отправит их в LLM, поставит оценки по трём критериям
(hard skills, experience, soft skills), рассчитает итоговый score 0-100
по взвешенной формуле и сохранит кандидата в историю для сравнения.

## Стек

- Python 3.11+
- Streamlit — веб-интерфейс
- OpenAI SDK через OpenAI-совместимый API (ProxyAPI) — запросы к модели
- pdfplumber — извлечение текста из PDF
- pandas — история кандидатов (CSV)

## Структура проекта

```
prescoring/
├── app.py            # интерфейс Streamlit, точка входа
├── parser.py         # извлечение и чистка текста из PDF (лимит 6000 символов)
├── gpt_service.py    # запрос к LLM, строгий JSON, ремонт JSON, расчёт score
├── storage.py        # история кандидатов (CSV)
├── test_parser.py    # быстрая проверка парсера
├── requirements.txt
├── .env.example      # шаблон переменных окружения
├── .gitignore
└── test_data/        # тестовые вакансия и резюме
```

## Запуск

1. Установите зависимости:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Скопируйте `.env.example` в `.env` и заполните ключ:
   ```
   copy .env.example .env
   ```
   В `.env` укажите ключ и адрес API провайдера:
   ```
   OPENAI_API_KEY=<ваш ключ>
   OPENAI_BASE_URL=https://api.proxyapi.ru/v1
   MODEL=gpt-4o-mini
   ```
   Проект работает с любым OpenAI-совместимым API — достаточно поменять
   `OPENAI_BASE_URL` и `MODEL`.
3. Запустите:
   ```
   streamlit run app.py
   ```

## Логика оценки

- Ответ модели — строго JSON: `hard_skills`, `experience`, `soft_skills`
  (0-100), `strengths`, `weaknesses`, `missing_skills`, `summary`.
- Итоговый score считается в коде по весам: hard 0.6, experience 0.25,
  soft 0.15 (по умолчанию; меняется слайдерами в интерфейсе, сумма
  нормализуется к 100%).
- Шкала: <50 — не подходит; 50-75 — частично подходит; >=75 — отлично.
- История сохраняется в `candidates_history.csv`; кандидатов можно
  сравнивать в интерфейсе и выгружать результат в JSON/CSV.
