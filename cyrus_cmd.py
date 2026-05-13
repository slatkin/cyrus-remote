#!/usr/bin/env python3
"""Send a single command to the cyrus daemon via Unix socket or TCP."""

import os
import socket
import sys

SOCK_PATH = os.path.join(
    os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"),
    "cyrus-remote.sock",
)
TCP_PORT = 9876


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Send a command to the cyrus daemon")
    parser.add_argument("command", help="mute  unmute  vol+  vol-  vol:<0-90>  input:<name>")
    parser.add_argument("--host", help="Remote daemon host (omit to use local Unix socket)")
    parser.add_argument("--port", type=int, default=TCP_PORT,
                        help=f"Remote daemon TCP port (default: {TCP_PORT})")
    args = parser.parse_args()

    try:
        if args.host:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((args.host, args.port))
                s.sendall((args.command + "\n").encode())
        else:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.connect(SOCK_PATH)
                s.sendall((args.command + "\n").encode())
    except FileNotFoundError:
        print("cyrus daemon not running", file=sys.stderr)
        sys.exit(1)
    except ConnectionRefusedError:
        print("cyrus daemon not responding", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"connection error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
