import argparse
import os
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or remove the job-search exclusion history table."
    )
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument(
        "--confirm-rollback",
        choices=["DROP_JOB_SEARCH_EXCLUSIONS"],
        help="Required with --rollback because rollback deletes exclusion history.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.rollback and args.confirm_rollback != "DROP_JOB_SEARCH_EXCLUSIONS":
        raise SystemExit("Rollback requires --confirm-rollback DROP_JOB_SEARCH_EXCLUSIONS")

    os.environ["DATABASE_URL"] = args.database_url

    from sqlalchemy import inspect

    from app.db.session import engine
    from app.models.job_search_exclusion import JobSearchExclusion

    table = JobSearchExclusion.__table__
    if args.rollback:
        table.drop(bind=engine, checkfirst=True)
        print("Rolled back job_search_exclusions.")
        return

    table.create(bind=engine, checkfirst=True)
    columns = {column["name"] for column in inspect(engine).get_columns(table.name)}
    expected = {
        "id",
        "user_id",
        "search_signature",
        "source_url",
        "title",
        "company_name",
        "blockers",
        "created_at",
        "last_seen_at",
    }
    if not expected.issubset(columns):
        raise SystemExit(f"Migration validation failed; missing columns: {sorted(expected - columns)}")
    print("Migrated and validated job_search_exclusions.")


if __name__ == "__main__":
    main()
