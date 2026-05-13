#!/usr/bin/env python3
"""Cyrus ONE BLE daemon — BLE loop + Unix socket for commands + Noctalia IPC push."""

import asyncio
import json
import os
import sys
from dataclasses import dataclass

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

DEFAULT_ADDRESS = "FD:6D:51:B8:5F:7E"
DEFAULT_ADAPTER = "hci0"
SERVICE_UUID    = "bc2f4cc6-aaef-4351-9034-d66268e328f0"
DATA_CHAR_UUID  = "06d1e5e7-79ad-4a71-8faa-373789f7d93c"

VOL_MIN, VOL_MAX = 0, 100

INPUTS = {
    "bt":      b"1",
    "usb":     b"2",
    "optical": b"3",
    "spdif":   b"4",
    "phono":   b"5",
    "aux5":    b"6",
    "aux6":    b"7",
    "av":      b"8",
}
INPUT_NAMES = {v[0]: k for k, v in INPUTS.items()}

_VOL_BREAKPOINTS = [
    0, 65, 68, 71, 74, 77, 80, 83, 86, 88, 90, 92, 94, 96, 98,
    100, 104, 108, 112, 116, 120, 123, 126, 129, 132, 135, 138,
    141, 144, 147, 150, 155, 160, 165, 170, 175, 180, 184, 188,
    192, 196, 200, 208, 215, 222, 229, 236, 243, 250, 266, 283,
    300, 316, 333, 350, 366, 383, 400, 416, 433, 450, 466, 483,
    500, 516, 533, 550, 566, 583, 600, 616, 633, 650, 666, 683,
    700, 716, 733, 750, 766, 783, 800, 850, 900, 950, 1000,
]

SOCK_PATH = os.path.join(
    os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"),
    "cyrus-remote.sock",
)


def raw_to_display(raw: int) -> int:
    for step, threshold in enumerate(_VOL_BREAKPOINTS):
        if raw <= threshold:
            return step
    return len(_VOL_BREAKPOINTS) - 1


def display_to_pct(step: int) -> int:
    return round(min(max(step, 0), VOL_MAX) * 100 / VOL_MAX)


@dataclass
class _State:
    connected: bool = False
    volume: int = 0
    muted: bool = False
    input_name: str = "--"


_state = _State()
_client: BleakClient | None = None
_loop: asyncio.AbstractEventLoop | None = None


async def push_state() -> None:
    payload = json.dumps({
        "connected": _state.connected,
        "vol": _state.volume,
        "vol_pct": display_to_pct(_state.volume),
        "muted": _state.muted,
        "input": _state.input_name,
    })
    proc = await asyncio.create_subprocess_exec(
        "qs", "-c", "noctalia-shell", "ipc", "call",
        "plugin:cyrus-remote", "updateState", payload,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()


def on_notify(char: BleakGATTCharacteristic, data: bytearray) -> None:
    raw = bytes(data)
    if len(raw) < 4 or raw[0:2] != b"@+":
        return
    cmd = chr(raw[2])
    payload = raw[3:-1] if raw[-1] == 0x25 else raw[3:]

    changed = False
    if cmd == "V":
        try:
            vol = int(payload[1:])  # payload = subtype_byte + step, e.g. b"248" → step 48
            if 0 <= vol <= VOL_MAX and _state.volume != vol:
                _state.volume = vol
                changed = True
        except (ValueError, IndexError):
            pass
    elif cmd == "M":
        muted = payload == b"11"
        if _state.muted != muted:
            _state.muted = muted
            changed = True
    elif cmd == "I":
        if len(payload) >= 2:
            name = INPUT_NAMES.get(payload[1], chr(payload[1]))
            if _state.input_name != name:
                _state.input_name = name
                changed = True

    if changed and _loop:
        asyncio.run_coroutine_threadsafe(push_state(), _loop)


async def handle_command(cmd: str) -> None:
    client = _client
    if client is None or not client.is_connected:
        return

    cmd = cmd.strip()
    data: bytes | None = None

    if cmd == "mute":
        data = b"@+M11%"
    elif cmd == "unmute":
        try:
            await client.write_gatt_char(DATA_CHAR_UUID, b"@+M10%", response=True)
            await asyncio.sleep(0.15)
            vol_data = b"@+V2" + f"{_state.volume:02d}".encode() + b"%"
            await client.write_gatt_char(DATA_CHAR_UUID, vol_data, response=True)
        except Exception as e:
            print(f"command error: {e}", file=sys.stderr)
        return
    elif cmd == "vol+":
        _state.volume = min(VOL_MAX, _state.volume + 1)
        data = b"@+V2" + f"{_state.volume:02d}".encode() + b"%"
    elif cmd == "vol-":
        _state.volume = max(VOL_MIN, _state.volume - 1)
        data = b"@+V2" + f"{_state.volume:02d}".encode() + b"%"
    elif cmd.startswith("vol:"):
        try:
            _state.volume = max(VOL_MIN, min(VOL_MAX, int(cmd[4:])))
            data = b"@+V2" + f"{_state.volume:02d}".encode() + b"%"
        except ValueError:
            pass
    elif cmd.startswith("input:"):
        src = cmd[6:]
        if src in INPUTS:
            data = b"@+I1" + INPUTS[src] + b"%"

    if data:
        is_vol_cmd = cmd in ("vol+", "vol-") or cmd.startswith("vol:")
        try:
            await client.write_gatt_char(DATA_CHAR_UUID, data, response=True)
            await push_state()
            if is_vol_cmd:
                await asyncio.sleep(0.15)
                await client.write_gatt_char(DATA_CHAR_UUID, b"@+F1V%", response=True)
        except Exception as e:
            print(f"command error: {e}", file=sys.stderr)


async def _socket_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        async for line in reader:
            await handle_command(line.decode())
    finally:
        writer.close()


async def serve_socket() -> None:
    if os.path.exists(SOCK_PATH):
        os.unlink(SOCK_PATH)
    server = await asyncio.start_unix_server(_socket_client, SOCK_PATH)
    async with server:
        await server.serve_forever()


async def connect_and_run(address: str, adapter: str) -> None:
    global _client
    print(f"Scanning for {address} on {adapter}…", file=sys.stderr)
    device = await BleakScanner.find_device_by_filter(
        lambda d, adv: (
            d.address.upper() == address.upper()
            or SERVICE_UUID.lower() in [str(u).lower() for u in adv.service_uuids]
            or "cyrus" in (d.name or "").lower()
            or (d.name or "").upper().startswith("ONE-")
        ),
        timeout=30.0,
        bluez={"adapter": adapter},
    )
    if device is None:
        raise RuntimeError("Device not found within 30s")

    print(f"Connected to {device.name}", file=sys.stderr)
    async with BleakClient(device, bluez={"adapter": adapter}) as client:
        _client = client
        _state.connected = True

        await client.start_notify(DATA_CHAR_UUID, on_notify)

        for letter in b"VMI":
            await client.write_gatt_char(DATA_CHAR_UUID,
                                         b"@+F1" + bytes([letter]) + b"%",
                                         response=True)
            await asyncio.sleep(0.15)

        await push_state()

        async def _periodic_sync() -> None:
            while client.is_connected:
                await asyncio.sleep(10)
                if client.is_connected:
                    try:
                        for letter in b"VMI":
                            await client.write_gatt_char(
                                DATA_CHAR_UUID, b"@+F1" + bytes([letter]) + b"%",
                                response=True,
                            )
                            await asyncio.sleep(0.15)
                    except Exception:
                        pass

        asyncio.ensure_future(_periodic_sync())

        while client.is_connected:
            await asyncio.sleep(0.5)

    _client = None


async def ble_loop(address: str, adapter: str) -> None:
    while True:
        try:
            await connect_and_run(address, adapter)
        except Exception as e:
            print(f"Disconnected: {e}. Reconnecting in 3s…", file=sys.stderr)
        _state.connected = False
        await push_state()
        await asyncio.sleep(3)


async def main(address: str, adapter: str) -> None:
    global _loop
    _loop = asyncio.get_running_loop()

    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: task.cancel())

    try:
        await asyncio.gather(
            ble_loop(address, adapter),
            serve_socket(),
        )
    except asyncio.CancelledError:
        pass
    finally:
        if _client and _client.is_connected:
            try:
                await _client.disconnect()
            except Exception:
                pass
        if os.path.exists(SOCK_PATH):
            os.unlink(SOCK_PATH)
        print("\nDaemon stopped.", file=sys.stderr)


if __name__ == "__main__":
    import argparse
    import signal
    parser = argparse.ArgumentParser(description="Cyrus ONE BLE daemon")
    parser.add_argument("-a", "--address", default=DEFAULT_ADDRESS,
                        help=f"BT address (default: {DEFAULT_ADDRESS})")
    parser.add_argument("--adapter", default=DEFAULT_ADAPTER,
                        help=f"HCI adapter (default: {DEFAULT_ADAPTER})")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.address, args.adapter))
    except (KeyboardInterrupt, SystemExit):
        pass
