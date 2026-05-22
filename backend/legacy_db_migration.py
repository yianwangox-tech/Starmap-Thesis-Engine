from __future__ import annotations

try:
    from backend.main import DB_FILE, LEGACY_DB_FILE, _merge_legacy_database
except ModuleNotFoundError:
    from main import DB_FILE, LEGACY_DB_FILE, _merge_legacy_database


def main() -> None:
    print(f"Current DB: {DB_FILE}")
    print(f"Legacy DB: {LEGACY_DB_FILE}")
    if not LEGACY_DB_FILE.exists():
        print("No legacy backend/database.db file found. Nothing to migrate.")
        return
    if LEGACY_DB_FILE.resolve() == DB_FILE.resolve():
        print("Legacy DB path matches the current DB path. Nothing to migrate.")
        return
    _merge_legacy_database()
    print("Legacy database merge completed.")


if __name__ == "__main__":
    main()
