from pathlib import Path
import json
import uuid
from datetime import datetime, timezone


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_ROOT / "data" / "problems.json"

VALID_STATUSES = ("new", "investigating", "solving", "solved", "failed", "archived")

UPDATEABLE_FIELDS = (
    "title", "description", "context", "error_message",
    "tags", "status", "solution", "cause", "helped", "related_record_id",
    "diagnostic",
)


class ProblemError(Exception):
    pass


def _new_id():
    return uuid.uuid4().hex[:12]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _default_problem(title, description, context, error_message, tags):
    return {
        "id": _new_id(),
        "created_at": _now_iso(),
        "title": title,
        "description": description,
        "context": context,
        "error_message": error_message,
        "tags": tags or [],
        "status": "new",
        "solution": "",
        "cause": "",
        "helped": None,
        "related_record_id": None,
    }


def load_problems():
    DATA_FILE.parent.mkdir(exist_ok=True)

    if not DATA_FILE.exists():
        return []

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise ProblemError(
            f"Файл данных повреждён: {DATA_FILE}\n{exc}"
        ) from exc

    if not isinstance(data, list):
        raise ProblemError(
            f"Ожидался список в {DATA_FILE}, получен {type(data).__name__}"
        )

    return data


def save_problems(problems):
    DATA_FILE.parent.mkdir(exist_ok=True)

    tmp = DATA_FILE.with_suffix(".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as file:
            json.dump(problems, file, ensure_ascii=False, indent=4)
        tmp.replace(DATA_FILE)
    except Exception as exc:
        if tmp.exists():
            tmp.unlink()
        raise ProblemError(f"Не удалось сохранить данные: {exc}") from exc


def create_problem(title, description="", context="", error_message="", tags=None):
    problems = load_problems()
    problem = _default_problem(title, description, context, error_message, tags)
    problems.append(problem)
    save_problems(problems)
    return problem


def get_problem(problem_id):
    problems = load_problems()
    for p in problems:
        if p.get("id") == problem_id:
            return p
    return None


def get_all_problems():
    return load_problems()


def update_problem(problem_id, **fields):
    problems = load_problems()
    for i, p in enumerate(problems):
        if p.get("id") == problem_id:
            for key in UPDATEABLE_FIELDS:
                if key in fields:
                    problems[i][key] = fields[key]
            save_problems(problems)
            return problems[i]
    return None


def delete_problem(problem_id):
    problems = load_problems()
    new_problems = [p for p in problems if p.get("id") != problem_id]
    if len(new_problems) == len(problems):
        return False
    save_problems(new_problems)
    return True


def _problem_to_search_record(problem):
    text_parts = []
    if problem.get("description"):
        text_parts.append(problem["description"])
    if problem.get("error_message"):
        text_parts.append(problem["error_message"])
    return {
        "id": problem["id"],
        "created_at": problem.get("created_at", ""),
        "type": "problem",
        "title": problem.get("title", ""),
        "text": "\n".join(text_parts),
        "tags": problem.get("tags", []),
    }


def search_problems(query):
    from src.search import rank_records

    if not query or not query.strip():
        return []

    problems = load_problems()
    search_records = [_problem_to_search_record(p) for p in problems]
    ranked = rank_records(query, search_records)
    ranked_ids = {r["id"] for r, _ in ranked}
    return [p for p in problems if p["id"] in ranked_ids]


def search_problems_with_scores(query):
    from src.search import rank_records

    if not query or not query.strip():
        return []

    problems = load_problems()
    search_records = [_problem_to_search_record(p) for p in problems]
    ranked = rank_records(query, search_records)
    id_to_problem = {p["id"]: p for p in problems}
    return [(id_to_problem[r["id"]], score) for r, score in ranked]
