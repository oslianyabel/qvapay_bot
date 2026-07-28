"""Entry point de la web app QvaPay P2P Monitor.

Uso:
    python web_main.py
    # o con recarga en desarrollo:
    uvicorn qvapay_web.app:app --reload
"""

from __future__ import annotations

import logging
import os

import uvicorn

from qvapay_bot.config import Settings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = Settings.from_env()
    reload = os.getenv("WEB_RELOAD", "false").strip().lower() in {"1", "true", "yes"}
    uvicorn.run(
        "qvapay_web.app:app",
        host=settings.web_host,
        port=settings.web_port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
