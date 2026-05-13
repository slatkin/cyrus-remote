#!/usr/bin/env python3
"""Send a single command to the cyrus daemon via its Unix socket."""

import os
import socket
import sys

SOCK_PATH = os.path.join(
    os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"),
    "cyrus-remote.sock",
)


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: cyrus-cmd <command>", file=sys.stderr)
        print("commands: mute  unmute  vol+  vol-  vol:<0-75>  input:<name>", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(SOCK_PATH)
            s.sendall((cmd + "\n").encode())
    except FileNotFoundError:
        print("cyrus daemon not running", file=sys.stderr)
        sys.exit(1)
    except ConnectionRefusedError:
        print("cyrus daemon not responding", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
