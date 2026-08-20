from pathlib import Path

MEMORY_FILES = [
    "memory/known-issues.md",
    "memory/pipeline-pitfalls.md",
    "memory/extractor-edge-cases.md",
    "memory/db-decisions.md",
]

def load_memory():
    contents = []

    for path in MEMORY_FILES:
        p = Path(path)
        if p.exists():
            contents.append(f"\n# {path}\n")
            contents.append(p.read_text(encoding="utf-8", errors="replace"))

    return "\n".join(contents)

if __name__ == "__main__":
    print(load_memory())