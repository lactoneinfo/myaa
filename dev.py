import subprocess
import sys

commands = {
    "lint": ["ruff", "check", "myaa"],
    "fix": ["ruff", "check", "myaa", "--fix"],
    "format": ["black", "myaa"],
    "check-format": ["black", "myaa", "--check"],
    "test": ["pytest"],
    "typecheck": ["mypy", "myaa", "--check-untyped-defs"],
    "check-all": [
        ["ruff", "check", "myaa"],
        ["black", "myaa", "--check"],
        ["mypy", "myaa", "--check-untyped-defs"]
    ]
}


def main():
    if len(sys.argv) < 2:
        print("Usage: python dev.py [lint|format|check-format|test]")
        return

    cmd = sys.argv[1]
    tasks = commands[cmd]
    if isinstance(tasks[0], list):
        for subcmd in tasks:
            print(f"▶ Running: {' '.join(subcmd)}")
            subprocess.run(subcmd)
    else:
        print(f"▶ Running: {' '.join(tasks)}")
        subprocess.run(tasks)

if __name__ == "__main__":
    main()
