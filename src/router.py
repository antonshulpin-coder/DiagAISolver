from src.commands import learn, solve_flow, build, knowledge


def route(choice):
    if choice == "1":
        learn()

    elif choice == "2":
        solve_flow()

    elif choice == "3":
        build()

    elif choice == "4":
        knowledge()

    elif choice == "0":
        print("\nДо встречи!")
        return False

    else:
        print("\n! Неверный пункт.")

    return True