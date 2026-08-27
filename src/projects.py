"""Хранилище и CRUD проектов.

Проект = большая цель, разбитая на подзадачи-проблемы. Проблема принадлежит не
более чем одному проекту (project_id); отсутствие проекта — норма.

Файл: data/projects.json, структура записи:
    {id, name, goal, created, status}  с status: active | done.

Запись атомарная (tmp + rename) — тот же паттерн, что в src/problems.py.
Файл отсутствует/пуст → пустой список; битый JSON → ProjectError с сообщением.
"""

from pathlib import Path
import json
import uuid
from datetime import datetime, timezone

from src import problems as _problems


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_ROOT / "data" / "projects.json"

VALID_STATUSES = ("active", "done")


class ProjectError(Exception):
    pass


def _new_id():
    return "p_" + uuid.uuid4().hex[:12]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _default_project(name, goal):
    return {
        "id": _new_id(),
        "name": name,
        "goal": goal,
        "created": _now_iso(),
        "status": "active",
    }


# ── Хранилище ────────────────────────────────────────────────────


def load_projects():
    DATA_FILE.parent.mkdir(exist_ok=True)

    if not DATA_FILE.exists():
        return []

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise ProjectError(
            f"Файл данных повреждён: {DATA_FILE}\n{exc}"
        ) from exc

    if not isinstance(data, list):
        raise ProjectError(
            f"Ожидался список в {DATA_FILE}, получен {type(data).__name__}"
        )

    return data


def save_projects(projects):
    DATA_FILE.parent.mkdir(exist_ok=True)

    tmp = DATA_FILE.with_suffix(".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as file:
            json.dump(projects, file, ensure_ascii=False, indent=4)
        tmp.replace(DATA_FILE)
    except Exception as exc:
        if tmp.exists():
            tmp.unlink()
        raise ProjectError(f"Не удалось сохранить проект: {exc}") from exc


# ── CRUD ─────────────────────────────────────────────────────────


def create_project(name, goal=""):
    name = (name or "").strip()
    if not name:
        raise ProjectError("Название проекта обязательно.")

    projects = load_projects()
    project = _default_project(name, (goal or "").strip())
    projects.append(project)
    save_projects(projects)
    return project


def get_project(project_id):
    for p in load_projects():
        if p.get("id") == project_id:
            return p
    return None


def get_all_projects():
    return load_projects()


def rename_project(project_id, name=None, goal=None):
    projects = load_projects()
    for p in projects:
        if p.get("id") == project_id:
            if name is not None:
                name = name.strip()
                if not name:
                    raise ProjectError("Название проекта не может быть пустым.")
                p["name"] = name
            if goal is not None:
                p["goal"] = goal.strip()
            save_projects(projects)
            return p
    return None


def set_project_status(project_id, status):
    if status not in VALID_STATUSES:
        raise ProjectError(f"Недопустимый статус проекта: {status}")

    projects = load_projects()
    for p in projects:
        if p.get("id") == project_id:
            p["status"] = status
            save_projects(projects)
            return p
    return None


def close_project(project_id):
    return set_project_status(project_id, "done")


def reopen_project(project_id):
    return set_project_status(project_id, "active")


def delete_project(project_id):
    """Удаляет проект из хранилища (сам по себе проблем не трогает)."""
    projects = load_projects()
    new_projects = [p for p in projects if p.get("id") != project_id]
    if len(new_projects) == len(projects):
        return False
    save_projects(new_projects)
    return True


# ── Привязка проблем ────────────────────────────────────────────


def problems_of_project(project_id):
    """Список проблем, привязанных к проекту (только чтение)."""
    return [p for p in _problems.load_problems() if p.get("project_id") == project_id]


def count_project_problems(project_id):
    return len(problems_of_project(project_id))


def bind_problem(problem_id, project_id):
    """Привязывает проблему к проекту; project_id=None отвязывает.

    Если проект указан и не существует — ProjectError. Возвращает обновлённую
    проблему или None (проблема не найдена).
    """
    if project_id is not None and get_project(project_id) is None:
        raise ProjectError(f"Проект не найден: {project_id}")
    return _problems.update_problem(problem_id, project_id=project_id)


def unbind_all_problems(project_id):
    """Отвязывает ВСЕ проблемы проекта (project_id = None). Проблемы не удаляет."""
    problems = _problems.load_problems()
    changed = False
    for p in problems:
        if p.get("project_id") == project_id:
            p["project_id"] = None
            changed = True
    if changed:
        _problems.save_problems(problems)
    return changed
