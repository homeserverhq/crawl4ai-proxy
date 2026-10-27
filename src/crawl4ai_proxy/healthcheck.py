from __future__ import annotations

import os
import sys
import urllib.request


def main() -> None:
    port = os.environ.get("LISTEN_PORT", "8000")
    url = f"http://127.0.0.1:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            if response.status != 200:
                raise RuntimeError(f"unexpected status {response.status}")
    except Exception as exc:
        print(f"healthcheck failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
