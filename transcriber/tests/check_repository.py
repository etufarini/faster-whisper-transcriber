"""
check_repository.py

Check source syntax and the boundary between development fixtures and release
assets without importing inference packages or reading user application data.
"""
import ast
import json
from pathlib import Path


# Inspect only tracked source families, ignoring environments and generated packages.
def main():
    root = Path(__file__).resolve().parents[1]
    sources = list((root / "engine").glob("*.py")) + list((root / "desktop/packaging").glob("*.py")) + list((root / "desktop/tests/fixtures").glob("*.py"))
    for path in sources:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    config = json.loads((root / "desktop/src-tauri/tauri.conf.json").read_text())
    assert "http://127.0.0.1" not in config["app"]["security"]["csp"]
    dist = root / "desktop/dist"
    if dist.exists():
        for path in dist.rglob("*.js"):
            text = path.read_text()
            assert "transcriber-fixture-export" not in text, "Development fixtures leaked into production assets"
    print("PASS: Python syntax, native-only production transport and fixture exclusion")


if __name__ == "__main__":
    main()
