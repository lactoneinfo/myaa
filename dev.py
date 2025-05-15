import subprocess
import sys

commands = {
    "lint": ["ruff", "check", "myaa"],
    "fix": ["ruff", "check", "myaa", "--fix"],
    "format": ["black", "myaa"],
    "check-format": ["black", "myaa", "--check"],
    "test": ["pytest"]
}

def main():
    if len(sys.argv) < 2:
        print("Usage: python dev.py [lint|format|check-format|test]")
        return

    cmd = sys.argv[1]
    if cmd not in commands:
        print(f"Unknown command: {cmd}")
        return

    print(f"▶ Running: {' '.join(commands[cmd])}")
    subprocess.run(commands[cmd])

if __name__ == "__main__":
    main()
