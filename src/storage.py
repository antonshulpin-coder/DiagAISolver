from pathlib import Path
import json
import uuid
from datetime import datetime, timezone


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_ROOT / "data" / "notes.json"


class StorageError(Exception):
    pass


def _new_id():
    return uuid.uuid4().hex[:12]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _is_old_format(record):
    return (
        isinstance(record, dict)
        and "text" in record
        and "id" not in record
    )


def _migrate_record(record):
    if _is_old_format(record):
        return {
            "id": _new_id(),
            "created_at": _now_iso(),
            "type": "note",
            "title": "",
            "text": record["text"],
            "tags": [],
        }
    return record


def load_notes():
    DATA_FILE.parent.mkdir(exist_ok=True)

    if not DATA_FILE.exists():
        return []

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as exc:
        raise StorageError(
            f"Файл данных повреждён: {DATA_FILE}\n{exc}"
        ) from exc

    if not isinstance(data, list):
        raise StorageError(
            f"Ожидался список в {DATA_FILE}, получен {type(data).__name__}"
        )

    migrated = [_migrate_record(r) for r in data]
    if migrated != data:
        save_notes(migrated)

    return migrated


def save_notes(notes):
    DATA_FILE.parent.mkdir(exist_ok=True)

    tmp = DATA_FILE.with_suffix(".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as file:
            json.dump(notes, file, ensure_ascii=False, indent=4)
        tmp.replace(DATA_FILE)
    except Exception as exc:
        if tmp.exists():
            tmp.unlink()
        raise StorageError(f"Не удалось сохранить данные: {exc}") from exc


def create_record(title, text, record_type="note", tags=None):
    notes = load_notes()
    record = {
        "id": _new_id(),
        "created_at": _now_iso(),
        "type": record_type,
        "title": title,
        "text": text,
        "tags": tags or [],
    }
    notes.append(record)
    save_notes(notes)
    return record


def get_record(record_id):
    notes = load_notes()
    for note in notes:
        if note.get("id") == record_id:
            return note
    return None


def get_all_records():
    return load_notes()


def update_record(record_id, **fields):
    notes = load_notes()
    for i, note in enumerate(notes):
        if note.get("id") == record_id:
            for key in ("title", "text", "type", "tags"):
                if key in fields:
                    notes[i][key] = fields[key]
            save_notes(notes)
            return notes[i]
    return None


def delete_record(record_id):
    notes = load_notes()
    new_notes = [n for n in notes if n.get("id") != record_id]
    if len(new_notes) == len(notes):
        return False
    save_notes(new_notes)
    return True


def search_records(query):
    from src.search import rank_records

    if not query or not query.strip():
        return []

    notes = load_notes()
    ranked = rank_records(query, notes)
    return [record for record, _score in ranked]


def search_records_with_scores(query):
    from src.search import rank_records

    if not query or not query.strip():
        return []

    notes = load_notes()
    return rank_records(query, notes)


def add_note(text):
    return create_record(title="", text=text)


def search_notes(query):
    return search_records(query)
