from crawler.pipeline import run_once
from crawler.runtime import load_settings


def main() -> None:
    settings = load_settings()
    run_once(settings)


if __name__ == "__main__":
    main()
