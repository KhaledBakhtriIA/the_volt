from __future__ import annotations

from argparse import ArgumentParser

from orchestration.jobs.prepare_kaggle_dataset import main as prepare_kaggle_main
from orchestration.jobs.run_once import main as run_once_main


def main() -> None:
    """Run production-safe pipeline entrypoints without notebook dependencies."""
    parser = ArgumentParser(description="Run Volt production data pipeline tasks.")
    parser.add_argument(
        "--prepare-kaggle",
        action="store_true",
        help="After collection, build/update stable Kaggle CSV export.",
    )
    args = parser.parse_args()

    run_once_main()
    if args.prepare_kaggle:
        prepare_kaggle_main()


if __name__ == "__main__":
    main()
