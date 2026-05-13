#!/usr/bin/env python3
"""Cyrus ONE BLE remote control — persistent connection REPL.

Protocol (all writes to DATA_CHAR_UUID, with-response):
    Mute on:  @+M11%      Mute off: @+M10%
    Input N:  @+I1N%      (N = 1..8)
    Volume:   @+V2<DD>%   (DD = display step 00..75, zero-padded)
    Fetch:    @+F1<C>%    (C = V/M/I/A to request current state)
"""

import asyncio
import atexit
import os
import readline
import sys

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

DEFAULT_ADDRESS = "FD:6D:51:B8:5F:7E"
SERVICE_UUID    = "bc2f4cc6-aaef-4351-9034-d66268e328f0"
DATA_CHAR_UUID  = "06d1e5e7-79ad-4a71-8faa-373789f7d93c"

VOL_MIN, VOL_MAX = 0, 75

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

def raw_to_display(raw: int) -> int:
    for step, threshold in enumerate(_VOL_BREAKPOINTS):
        if raw <= threshold:
            return step
    return len(_VOL_BREAKPOINTS) - 1


def on_notify(char: BleakGATTCharacteristic, data: bytearray) -> None:
    raw = bytes(data)
    if len(raw) < 4 or raw[0:2] != b"@+":
        return
    cmd = chr(raw[2])
    payload = raw[3:-1] if raw[-1] == 0x25 else raw[3:]
    if cmd == "V":
        try:
            vol_raw = int(payload)
            print(f"  volume: {raw_to_display(vol_raw)}/75  (raw {vol_raw})")
        except ValueError:
            pass
    elif cmd == "M":
        if payload == b"10":
            print("  mute: off")
        elif payload == b"11":
            print("  mute: on")
    elif cmd == "I":
        if len(payload) >= 2:
            name = INPUT_NAMES.get(payload[1], chr(payload[1]))
            print(f"  input: {name}")
    elif cmd == "A":
        if payload == b"10":
            print("  av-direct: off")
        elif payload == b"11":
            print("  av-direct: on")


def parse_cmd(line: str) -> bytes | None:
    """Parse a text command and return the BLE bytes to send, or None on error."""
    parts = line.strip().split()
    if not parts:
        return None
    cmd = parts[0].lower()

    if cmd in ("mute", "m"):
        return b"@+M11%"
    if cmd in ("unmute", "um"):
        return b"@+M10%"
    if cmd in ("status", "s"):
        return b""   # special: send multiple fetches
    if cmd in ("volume", "vol", "v"):
        if len(parts) < 2:
            print("  usage: volume <0-75>")
            return None
        try:
            level = int(parts[1])
        except ValueError:
            print("  volume must be a number 0-75")
            return None
        level = max(VOL_MIN, min(VOL_MAX, level))
        dd = f"{level:02d}".encode()
        return b"@+V2" + dd + b"%"
    if cmd in ("input", "i"):
        if len(parts) < 2:
            print("  inputs: " + " ".join(INPUTS))
            return None
        src = parts[1].lower()
        if src not in INPUTS:
            print(f"  unknown input '{src}'. choices: " + " ".join(INPUTS))
            return None
        return b"@+I1" + INPUTS[src] + b"%"
    if cmd in ("help", "?", "h"):
        print("  commands: mute  unmute  volume <0-75>  input <"
              + "|".join(INPUTS) + ">  status  quit")
        return None
    if cmd in ("quit", "q", "exit"):
        raise SystemExit(0)
    print(f"  unknown command '{cmd}'. type 'help' for list.")
    return None


DEFAULT_ADAPTER = "hci0"


async def find_device(address: str, adapter: str) -> object:
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
        sys.exit("Device not found.")
    print(f"Found: {device.name} ({device.address})", file=sys.stderr)
    return device


async def repl(address: str, adapter: str) -> None:
    device = await find_device(address, adapter)

    async with BleakClient(device, bluez={"adapter": adapter}) as client:
        print(f"Connected to {device.name}. Type 'help' for commands, 'quit' to exit.\n")
        await client.start_notify(DATA_CHAR_UUID, on_notify)

        # Print initial status on connect
        for letter in b"VMIA":
            await client.write_gatt_char(DATA_CHAR_UUID,
                                         b"@+F1" + bytes([letter]) + b"%",
                                         response=True)
            await asyncio.sleep(0.15)

        loop = asyncio.get_event_loop()

        while True:
            # Read a line without blocking the asyncio event loop
            try:
                line = await loop.run_in_executor(None, lambda: input("> "))
            except (EOFError, KeyboardInterrupt):
                break

            try:
                cmd_bytes = parse_cmd(line)
            except SystemExit:
                break

            if cmd_bytes is None:
                continue

            try:
                if cmd_bytes == b"":
                    # status: fetch each item
                    for letter in b"VMIA":
                        await client.write_gatt_char(DATA_CHAR_UUID,
                                                     b"@+F1" + bytes([letter]) + b"%",
                                                     response=True)
                        await asyncio.sleep(0.15)
                else:
                    await client.write_gatt_char(DATA_CHAR_UUID, cmd_bytes, response=True)
                    await asyncio.sleep(0.3)
            except Exception as e:
                print(f"  error: {e}")
                print("  reconnecting…")
                break


async def main_loop(address: str, adapter: str) -> None:
    """Keep reconnecting if the connection drops."""
    while True:
        try:
            await repl(address, adapter)
        except SystemExit:
            raise
        except Exception as e:
            print(f"\nDisconnected ({e}). Reconnecting in 3s…", file=sys.stderr)
            await asyncio.sleep(3)


def _setup_history() -> None:
    state_home = os.environ.get("XDG_STATE_HOME", os.path.join(os.path.expanduser("~"), ".local", "state"))
    history_dir = os.path.join(state_home, "cyrus-remote")
    os.makedirs(history_dir, exist_ok=True)
    history_file = os.path.join(history_dir, "history")
    try:
        readline.read_history_file(history_file)
    except FileNotFoundError:
        pass
    readline.set_history_length(500)
    atexit.register(readline.write_history_file, history_file)


if __name__ == "__main__":
    import argparse
    _setup_history()
    parser = argparse.ArgumentParser(description="Cyrus ONE BLE remote")
    parser.add_argument("-a", "--address", default=DEFAULT_ADDRESS,
                        help=f"BT address (default: {DEFAULT_ADDRESS})")
    parser.add_argument("--adapter", default=DEFAULT_ADAPTER,
                        help=f"HCI adapter (default: {DEFAULT_ADAPTER})")
    args = parser.parse_args()

    try:
        asyncio.run(main_loop(args.address, args.adapter))
    except (SystemExit, KeyboardInterrupt):
        print("\nBye.")
