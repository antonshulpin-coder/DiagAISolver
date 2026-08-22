from pathlib import Path
import json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS_FILE = PROJECT_ROOT / "config" / "settings.json"


def get_academy_root():
    """Возвращает путь к локальному источнику материалов Академии."""
    try:
        settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return Path(settings["academy_root"])
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


def _markdown_files(book_path):
    return sorted(book_path.glob("*.md"), key=lambda item: item.name)


def browse_academy():
    """Позволяет выбрать и прочитать материал из локальной Академии."""
    academy_root = get_academy_root()
    if academy_root is None or not academy_root.exists():
        print("\nАкадемия пока не найдена.")
        print(f"Проверьте путь в настройках: {SETTINGS_FILE}")
        return

    books_root = academy_root / "01_BOOKS"
    if not books_root.exists():
        print("\nВ Академии не найдена папка с учебными томами.")
        return
    books = sorted((item for item in books_root.iterdir() if item.is_dir()), key=lambda item: item.name)

    if not books:
        print("\nВ Академии пока нет учебных томов.")
        return

    while True:
        print("\n====== АКАДЕМИЯ МАРКЕТИНГА ======")
        for number, book in enumerate(books, start=1):
            print(f"{number}. {book.name.replace('_', ' ')}")
        print("0. Назад")

        choice = input("\nВыберите том: ").strip()
        if choice == "0":
            return

        if not choice.isdigit() or not 1 <= int(choice) <= len(books):
            print("\nНеверный выбор.")
            continue

        browse_book(books[int(choice) - 1])


def browse_book(book_path):
    chapters = _markdown_files(book_path)

    while True:
        print(f"\n====== {book_path.name.replace('_', ' ')} ======")
        for number, chapter in enumerate(chapters, start=1):
            print(f"{number}. {chapter.stem.replace('_', ' ')}")
        print("0. Назад")

        choice = input("\nВыберите материал: ").strip()
        if choice == "0":
            return

        if not choice.isdigit() or not 1 <= int(choice) <= len(chapters):
            print("\nНеверный выбор.")
            continue

        chapter = chapters[int(choice) - 1]
        print("\n" + "=" * 50)
        print(chapter.read_text(encoding="utf-8-sig"))
        input("\nНажмите Enter, чтобы вернуться к оглавлению тома...")
