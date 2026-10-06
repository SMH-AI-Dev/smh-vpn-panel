"""Run the panel: python -m smhpanel [--host H] [--port P] [--config PATH]."""
from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="smhpanel")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--config", default=None)
    args = parser.parse_args()

    if args.config:
        os.environ["SMHPANEL_CONFIG"] = str(args.config)

    from .config import load_config
    from .main import create_app
    import uvicorn

    config = load_config(args.config)
    app = create_app(config)

    host = args.host or "0.0.0.0"
    port = args.port or int(config.get("panel.port", 2053))

    kwargs = {}
    certfile = config.get("panel.tls.certfile")
    keyfile = config.get("panel.tls.keyfile")
    if (
        config.get("panel.tls.enabled")
        and certfile
        and keyfile
        and Path(certfile).exists()
    ):
        kwargs["ssl_certfile"] = certfile
        kwargs["ssl_keyfile"] = keyfile

    uvicorn.run(app, host=host, port=port, log_level="info", **kwargs)


if __name__ == "__main__":
    main()
