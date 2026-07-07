import json
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "survey_schema.json"
ANSWERS_PATH = Path(__file__).resolve().parent.parent / "answer_guidelines.json"


def load_schema() -> dict[str, Any]:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_answers() -> dict[str, Any]:
    if ANSWERS_PATH.exists():
        with open(ANSWERS_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_answers(answers: dict[str, Any]) -> None:
    with open(ANSWERS_PATH, "w", encoding="utf-8") as f:
        json.dump(answers, f, indent=2, ensure_ascii=False)


def count_questions(schema: dict[str, Any]) -> int:
    return sum(len(s["questions"]) for s in schema["sections"])


def get_all_questions(schema: dict[str, Any]) -> list[dict[str, Any]]:
    questions = []
    for section in schema["sections"]:
        for q in section["questions"]:
            questions.append({**q, "section": section["title"], "section_id": section["id"]})
    return questions
