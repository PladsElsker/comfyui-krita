import argparse
import sys
import time
from http import HTTPStatus
import socket
import requests


def wait_for_server(url: str, timeout: int) -> int:
    """Poll the server until it responds with status 200 or timeout expires."""
    start = time.time()
    while True:
        local_ports = open_tcp_ports()
        print(f"Open local TCP ports: {local_ports}", flush=True)  # noqa: T201

        try:
            r = requests.get(f"{url}/system_stats", timeout=1)
            if r.status_code == HTTPStatus.OK:
                return 0
        except requests.exceptions.RequestException:
            pass

        if time.time() - start > timeout:
            return 1

        time.sleep(0.5)


def open_tcp_ports(host="127.0.0.1", start=1, end=65535):
    ports = []
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.05)
            if s.connect_ex((host, port)) == 0:
                ports.append(port)
    return ports


def main() -> None:
    parser = argparse.ArgumentParser(description="Wait for ComfyUI server to start")
    parser.add_argument("--url", type=str, default="http://127.0.0.1:8188", help="URL of the ComfyUI server to poll")
    parser.add_argument("--timeout", type=int, default=20, help="Maximum number of seconds to wait")
    args = parser.parse_args()
    exit_code = wait_for_server(args.url, args.timeout)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
