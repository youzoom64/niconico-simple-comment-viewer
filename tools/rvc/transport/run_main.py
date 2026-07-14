from __future__ import annotations

from pathlib import Path

import uvicorn

from rvc_lan_transport.config import MainConfig
from rvc_lan_transport.main_service import create_main_app


def main() -> None:
    root = Path(__file__).resolve().parent
    config = MainConfig.from_env(root / ".env")
    uvicorn.run(create_main_app(config), host=config.status_host, port=config.status_port, access_log=False)


if __name__ == "__main__":
    main()
