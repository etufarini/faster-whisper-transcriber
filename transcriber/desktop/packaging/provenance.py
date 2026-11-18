"""
provenance.py

Record the packaged environment and copy dependency license notices. This build
tool never loads a model or accesses an inference service.
"""
from importlib import metadata
import json
from pathlib import Path
import platform
import sys


# Keep upstream notices alongside pinned versions, including native wheel packages.
def main():
    output = Path(sys.argv[1])
    packages = []
    notices = []
    for distribution in sorted(metadata.distributions(), key=lambda item: item.metadata["Name"].lower()):
        name = distribution.metadata["Name"]
        packages.append({"name": name, "version": distribution.version, "license": distribution.metadata.get("License-Expression") or distribution.metadata.get("License")})
        for entry in distribution.files or []:
            if entry.name.lower().startswith(("license", "copying", "notice")):
                path = distribution.locate_file(entry)
                if path.is_file():
                    notices.append(f"\n===== {name} {distribution.version}: {entry} =====\n" + path.read_text(encoding="utf-8", errors="replace"))
    output.mkdir(parents=True, exist_ok=True)
    (output / "dependency-provenance.json").write_text(json.dumps({"python": platform.python_version(), "platform": platform.platform(), "packages": packages}, indent=2) + "\n", encoding="utf-8")
    (output / "THIRD-PARTY-NOTICES.txt").write_text("".join(notices), encoding="utf-8")


if __name__ == "__main__":
    main()
