# uv run python main.py
import logging

from qvapay_bot.config import Settings
from qvapay_bot.handlers import build_application


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def main() -> None:
    configure_logging()
    settings = Settings.from_env()
    app = build_application(settings)
    app.run_polling()


if __name__ == "__main__":
    main()
