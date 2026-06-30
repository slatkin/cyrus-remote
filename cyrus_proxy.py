#!/usr/bin/env python3
"""Cyrus proxy — relay state from desktop daemon to local Noctalia; relay commands back."""

import asyncio
import json
import os
import sys

SOCK_PATH = os.path.join(
    os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"),
    "cyrus-remote.sock",
)
DEFAULT_PORT = 9876


async def _ipc_push(entry: str, payload: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        "noctalia", "msg", "plugin", f"slatkin/cyrus:{entry}",
        "all", "updateState", payload,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()


async def ipc_push(payload: str) -> None:
    await asyncio.gather(
        _ipc_push("volume", payload),
        _ipc_push("input", payload),
    )


async def _local_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                        tcp_writer: asyncio.StreamWriter) -> None:
    try:
        async for line in reader:
            tcp_writer.write(line)
            await tcp_writer.drain()
    except Exception:
        pass
    finally:
        writer.close()


async def _serve_proxy(host: str, port: int) -> None:
    print(f"Connecting to {host}:{port}…", file=sys.stderr)
    reader, writer = await asyncio.open_connection(host, port)
    print("Connected.", file=sys.stderr)

    if os.path.exists(SOCK_PATH):
        os.unlink(SOCK_PATH)

    server = await asyncio.start_unix_server(
        lambda r, w: _local_client(r, w, writer),
        SOCK_PATH,
    )

    async def _read_state() -> None:
        try:
            async for line in reader:
                data = line.decode().strip()
                if data:
                    await ipc_push(data)
        finally:
            server.close()

    async with server:
        await _read_state()

    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


async def _proxy_loop(host: str, port: int) -> None:
    while True:
        try:
            await _serve_proxy(host, port)
        except Exception as e:
            print(f"Disconnected: {e}. Reconnecting in 3s…", file=sys.stderr)
        await ipc_push(json.dumps({
            "connected": False, "vol": 0, "vol_pct": 0,
            "muted": False, "input": "--",
        }))
        if os.path.exists(SOCK_PATH):
            os.unlink(SOCK_PATH)
        await asyncio.sleep(3)


async def main(host: str, port: int) -> None:
    import signal
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: task.cancel())
    try:
        await _proxy_loop(host, port)
    except asyncio.CancelledError:
        pass
    finally:
        if os.path.exists(SOCK_PATH):
            os.unlink(SOCK_PATH)
        print("\nProxy stopped.", file=sys.stderr)


if __name__ == "__main__":
    import argparse
    import signal
    parser = argparse.ArgumentParser(description="Cyrus proxy for remote Noctalia instances")
    parser.add_argument("--host", required=True, help="Desktop daemon hostname or IP")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Daemon TCP port (default: {DEFAULT_PORT})")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.host, args.port))
    except (KeyboardInterrupt, SystemExit):
        pass
