from pathlib import Path
import json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = PROJECT_ROOT / "data" / "notes.json"


def load_notes():
    """Загружает заметки из файла."""
    DATA_FILE.parent.mkdir(exist_ok=True)

    if not DATA_FILE.exists():
        return []

    with DATA_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_notes(notes):
    """Сохраняет список заметок."""
    DATA_FILE.parent.mkdir(exist_ok=True)

    with DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(notes, file, ensure_ascii=False, indent=4)


def add_note(text):
    """Добавляет новую заметку."""
    notes = load_notes()

    notes.append({
        "text": text
    })

    save_notes(notes)


def search_notes(query):
    """Ищет заметки по тексту."""
    notes = load_notes()

    query = query.lower().strip()

    results = []

    for note in notes:
        if query in note["text"].lower():
            results.append(note)

    return results
