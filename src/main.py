from src.ui import show_header
from src.menu import show_menu
from src.router import route


def main():
    running = True

    while running:
        show_header()
        show_menu()

        choice = input("\nВыберите пункт: ")

        running = route(choice)

        if running:
            input("\nНажмите Enter, чтобы продолжить...")
            