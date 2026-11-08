"""HR-прескоринг кандидатов — веб-интерфейс (Streamlit)."""

import json
import os

import streamlit as st
from dotenv import load_dotenv

import gpt_service
import storage
from parser import parse_resume

load_dotenv()

DEFAULT_WEIGHTS = (60, 25, 15)
COLOR_RED, COLOR_YELLOW, COLOR_GREEN = "#e53935", "#f9a825", "#43a047"

st.set_page_config(
    page_title="Прескоринг кандидатов",
    page_icon="📋",
    layout="wide",
)

st.title("ИИ-прескоринг кандидатов")
st.caption(
    "Загрузите вакансию и PDF-резюме — сервис оценит соответствие "
    "кандидата вакансии по 100-балльной шкале."
)


def score_color(score: int) -> str:
    if score < 50:
        return COLOR_RED
    if score < 75:
        return COLOR_YELLOW
    return COLOR_GREEN


def verdict_text(score: int) -> str:
    if score < 50:
        return "Кандидат не подходит"
    if score < 75:
        return "Кандидат частично подходит"
    return "Отличный результат"


# ---------- Сайдбар: веса и модель ----------
st.sidebar.header("Веса критериев")
st.sidebar.caption("Сумма должна быть равна 100%. Сумма != 100% нормализуется автоматически.")
w_hard = st.sidebar.slider("Hard skills, %", 0, 100, DEFAULT_WEIGHTS[0], step=5)
w_experience = st.sidebar.slider("Experience, %", 0, 100, DEFAULT_WEIGHTS[1], step=5)
w_soft = st.sidebar.slider("Soft skills, %", 0, 100, DEFAULT_WEIGHTS[2], step=5)
w_total = w_hard + w_experience + w_soft
if w_total != 100:
    st.sidebar.warning(f"Сумма весов = {w_total}% — будет нормализована к 100%.")

st.sidebar.divider()
model_name = st.sidebar.text_input("Модель", value=os.getenv("MODEL", "gpt-4o-mini"))

# ---------- Ввод данных ----------
vacancy_text = st.text_area(
    "Текст вакансии",
    height=220,
    placeholder="Вставьте описание вакансии и требования...",
)
name = st.text_input("Имя кандидата", placeholder="Иван Иванов")
pdf_file = st.file_uploader("Резюме кандидата (PDF)", type=["pdf"])

if st.button("Оценить кандидата", type="primary", width="stretch"):
    if not vacancy_text.strip():
        st.error("Вставьте текст вакансии.")
    elif pdf_file is None:
        st.error("Загрузите PDF-резюме кандидата.")
    else:
        with st.spinner("Парсим резюме и оцениваем кандидата..."):
            pdf_file.seek(0)
            resume_text = parse_resume(pdf_file)
            if not resume_text:
                st.error(
                    "Не удалось извлечь текст из PDF. Файл может быть "
                    "сканом-изображением без текстового слоя."
                )
            else:
                try:
                    analysis = gpt_service.analyze_candidate(
                        vacancy_text, resume_text, model=model_name
                    )
                except Exception as exc:  # noqa: BLE001 — показываем пользователю
                    st.error(f"Ошибка обращения к модели: {exc}")
                else:
                    score = gpt_service.final_score(
                        analysis["hard_skills"],
                        analysis["experience"],
                        analysis["soft_skills"],
                        (w_hard, w_experience, w_soft),
                    )
                    record = storage.append_record(
                        name,
                        model_name,
                        analysis["hard_skills"],
                        analysis["experience"],
                        analysis["soft_skills"],
                        score,
                        f"{w_hard}/{w_experience}/{w_soft}",
                        analysis,
                    )
                    st.session_state["last_record"] = record
                    st.session_state["last_analysis"] = analysis

# ---------- Результат последней оценки ----------
record = st.session_state.get("last_record")
if record:
    analysis = st.session_state.get("last_analysis", {})
    color = score_color(record["score"])
    st.divider()
    st.markdown(f"### Кандидат: {record['name']}")
    st.markdown(
        f"<h2 style='color:{color};'>Итоговый score: {record['score']} / 100 — "
        f"{verdict_text(record['score'])}</h2>",
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns(3)
    col1.metric("Hard skills", record["hard_skills"])
    col2.metric("Experience", record["experience"])
    col3.metric("Soft skills", record["soft_skills"])
    if analysis.get("summary"):
        st.markdown(f"**Вывод:** {analysis['summary']}")

    col_a, col_b = st.columns(2)
    with col_a:
        with st.expander("Сильные стороны", expanded=True):
            if analysis.get("strengths"):
                for item in analysis["strengths"]:
                    st.markdown(f"- {item}")
            else:
                st.caption("Не указаны.")
    with col_b:
        with st.expander("Слабые стороны", expanded=True):
            if analysis.get("weaknesses"):
                for item in analysis["weaknesses"]:
                    st.markdown(f"- {item}")
            else:
                st.caption("Не указаны.")
    with st.expander("Недостающие навыки (missing_skills)", expanded=True):
        if analysis.get("missing_skills"):
            for item in analysis["missing_skills"]:
                st.markdown(f"- {item}")
        else:
            st.caption("Не указаны.")

    st.download_button(
        "Скачать результат (JSON)",
        data=storage.candidate_json(record),
        file_name=f"candidate_{record['token']}.json",
        mime="application/json",
    )

# ---------- История кандидатов ----------
st.divider()
st.header("История кандидатов")
history = storage.load_history()
if history.empty:
    st.info("История пуста — оцените первого кандидата.")
else:
    st.caption(f"Всего кандидатов в истории: {len(history)}")
    view = history.sort_values("score", ascending=False)
    st.dataframe(
        view[["name", "datetime", "score", "hard_skills", "experience",
              "soft_skills", "model"]],
        width="stretch",
        hide_index=True,
    )

    st.download_button(
        "Скачать историю (CSV)",
        data=open(storage.HISTORY_PATH, "rb").read(),
        file_name="candidates_history.csv",
        mime="text/csv",
    )

    st.subheader("Сравнение кандидатов")
    names = st.multiselect(
        "Выберите кандидатов для сравнения",
        options=list(dict.fromkeys(history["name"].tolist())),
    )
    if names:
        selected = history[history["name"].isin(names)].sort_values("score", ascending=False)
        st.dataframe(
            selected[["name", "score", "hard_skills", "experience",
                      "soft_skills", "summary"]],
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("Выберите одного или нескольких кандидатов из списка.")
