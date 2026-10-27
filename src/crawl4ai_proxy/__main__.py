from __future__ import annotations

import logging

import uvicorn

from .app import create_app
from .config import Settings


def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    uvicorn.run(
        create_app(settings),
        host=settings.listen_ip,
        port=settings.listen_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
