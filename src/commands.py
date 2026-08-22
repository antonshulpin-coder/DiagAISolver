from src.academy import browse_academy
from src.storage import add_note, load_notes, search_notes


def learn():
    browse_academy()


def solve():
    print("\n🛠️ Режим решения проблем пока в разработке.")


def build():
    print("\n🚀 Режим создания проектов пока в разработке.")


def knowledge():
    while True:
        print("\n====== БАЗА ЗНАНИЙ ======")
        print("1. Добавить заметку")
        print("2. Посмотреть заметки")
        print("3. Поиск")
        print("0. Назад")

        choice = input("\nВыберите пункт: ")

        if choice == "1":
            text = input("\nВведите заметку: ")
            if text.strip():
                add_note(text)
                print("\n✅ Заметка сохранена.")

        elif choice == "2":
            notes = load_notes()
            if not notes:
                print("\nЗаметок пока нет.")
            else:
                print("\n====== МОИ ЗАМЕТКИ ======\n")
                for number, note in enumerate(notes, start=1):
                    print(f"{number}. {note['text']}")

        elif choice == "3":
            query = input("\nВведите запрос: ")
            results = search_notes(query)
            if not results:
                print("\nНичего не найдено.")
            else:
                print("\n====== РЕЗУЛЬТАТЫ ПОИСКА ======\n")
                for number, note in enumerate(results, start=1):
                    print(f"{number}. {note['text']}")

        elif choice == "0":
            break

        else:
            print("\nНеверный выбор.")

        input("\nНажмите Enter...")
