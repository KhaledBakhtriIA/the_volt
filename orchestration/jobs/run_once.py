from pprint import pprint

from infrastructure.config.settings import get_settings
from orchestration.jobs.pipeline import run_full_collection


def main() -> None:
    """Run one deterministic full collection cycle outside notebook execution."""
    settings = get_settings()
    result = run_full_collection(settings)
    pprint(result)


if __name__ == "__main__":
    main()
