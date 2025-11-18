import os
import socket
import sys
import time

host = os.environ.get("KRITA_DEBUG_HOST", "127.0.0.1")
port = int(os.environ.get("KRITA_DEBUG_PORT", 5678))  # noqa: PLW1508
timeout = 10


start = time.time()
while time.time() - start < timeout:
    try:
        with socket.create_connection((host, port), timeout=1):
            sys.exit(0)
    except Exception:  # noqa: BLE001
        time.sleep(0.5)


print(f"Timeout waiting for debugger at {host}:{port}", file=sys.stderr)  # noqa: T201
sys.exit(1)
