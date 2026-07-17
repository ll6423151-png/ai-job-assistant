import argparse
import os
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add or remove jobs.is_archived.")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument(
        "--confirm-rollback",
        choices=["DROP_JOB_ARCHIVING"],
        help="Required with --rollback.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.rollback and args.confirm_rollback != "DROP_JOB_ARCHIVING":
        raise SystemExit("Rollback requires --confirm-rollback DROP_JOB_ARCHIVING")
    os.environ["DATABASE_URL"] = args.database_url

    from sqlalchemy import inspect, text

    from app.db.session import engine

    columns = {column["name"] for column in inspect(engine).get_columns("jobs")}
    with engine.begin() as connection:
        if args.rollback:
            if "is_archived" in columns:
                connection.execute(text("ALTER TABLE jobs DROP COLUMN is_archived"))
        elif "is_archived" not in columns:
            connection.execute(
                text("ALTER TABLE jobs ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT FALSE")
            )

    migrated_columns = {
        column["name"] for column in inspect(engine).get_columns("jobs")
    }
    expected_present = not args.rollback
    if ("is_archived" in migrated_columns) != expected_present:
        raise SystemExit("Job archiving migration validation failed")
    action = "Rolled back" if args.rollback else "Migrated and validated"
    print(f"{action} jobs.is_archived.")


if __name__ == "__main__":
    main()
