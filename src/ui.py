from pathlib import Path
import tomllib


def _read_version():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    try:
        with pyproject.open("rb") as f:
            return tomllib.load(f)["project"]["version"]
    except Exception:
        return "0.0.0"


def show_header():
    version = _read_version()
    print("=" * 50)
    print(f"        ANTON HARNESS v{version}")
    print("=" * 50)
