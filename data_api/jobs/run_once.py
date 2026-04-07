from pprint import pprint

from data_api.config.settings import get_settings
from data_api.jobs.pipeline import run_full_collection


def main() -> None:
    """Run one deterministic full collection cycle outside notebook execution."""
    settings = get_settings()
    result = run_full_collection(settings)
    pprint(result)


if __name__ == "__main__":
    main()
