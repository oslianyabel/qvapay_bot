import asyncio
import logging

from qvapay_bot.config import Settings
from qvapay_bot.telegram_bot import QvaPayTelegramBot


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


async def main() -> None:
    configure_logging()
    settings = Settings.from_env()
    bot = QvaPayTelegramBot(settings=settings)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
