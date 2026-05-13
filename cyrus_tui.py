#!/usr/bin/env python3
"""Cyrus ONE BLE remote control — Textual TUI."""

import asyncio
import argparse

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Label, ProgressBar, RichLog, Select

DEFAULT_ADDRESS = "FD:6D:51:B8:5F:7E"
DEFAULT_ADAPTER = "hci0"
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


class CyrusApp(App):
    TITLE = "Cyrus ONE Remote"

    CSS = """
    Screen {
        layout: vertical;
        padding: 1 2;
    }

    #vol_label {
        text-align: center;
    }

    #vol_bar {
        margin-bottom: 1;
    }

    #controls {
        height: 3;
        margin-bottom: 1;
    }

    #input_select {
        width: 1fr;
    }

    #mute_btn {
        width: 12;
        margin-left: 1;
    }

    #mute_btn.muted {
        color: $warning;
    }

    #log {
        border: round $primary;
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("+", "volume_up", "Vol +"),
        Binding("=", "volume_up", "Vol +", show=False),
        Binding("-", "volume_down", "Vol -"),
        Binding("m", "toggle_mute", "Mute"),
        Binding("s", "fetch_status", "Status"),
        Binding("q", "quit", "Quit"),
    ]

    volume: reactive[int] = reactive(0, init=False)
    muted: reactive[bool] = reactive(False, init=False)

    def __init__(self, address: str = DEFAULT_ADDRESS, adapter: str = DEFAULT_ADAPTER) -> None:
        super().__init__()
        self.address = address
        self.adapter = adapter
        self._client: BleakClient | None = None
        self._known_input: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Volume: --/75", id="vol_label")
        yield ProgressBar(total=75, show_eta=False, id="vol_bar")
        with Horizontal(id="controls"):
            yield Select(
                [(k, k) for k in INPUTS],
                prompt="Input…",
                id="input_select",
            )
            yield Button("Mute", id="mute_btn")
        yield RichLog(id="log", markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self._ble_loop()

    @work(exclusive=True)
    async def _ble_loop(self) -> None:
        while True:
            try:
                await self._connect_and_run()
            except Exception as e:
                self._log(f"[red]Disconnected: {e}. Reconnecting in 3s…[/]")
                await asyncio.sleep(3)

    async def _connect_and_run(self) -> None:
        self._log(f"Scanning for {self.address} on {self.adapter}…")
        device = await BleakScanner.find_device_by_filter(
            lambda d, adv: (
                d.address.upper() == self.address.upper()
                or SERVICE_UUID.lower() in [str(u).lower() for u in adv.service_uuids]
                or "cyrus" in (d.name or "").lower()
                or (d.name or "").upper().startswith("ONE-")
            ),
            timeout=30.0,
            bluez={"adapter": self.adapter},
        )
        if device is None:
            raise RuntimeError("Device not found within 30s")

        self._log(f"[green]Connected to {device.name} ({device.address})[/]")
        async with BleakClient(device, bluez={"adapter": self.adapter}) as client:
            self._client = client
            await client.start_notify(DATA_CHAR_UUID, self._on_notify)
            for letter in b"VMIA":
                await client.write_gatt_char(
                    DATA_CHAR_UUID, b"@+F1" + bytes([letter]) + b"%", response=True
                )
                await asyncio.sleep(0.15)
            while client.is_connected:
                await asyncio.sleep(0.5)
        self._client = None
        self._log("[yellow]Connection closed.[/]")

    def _on_notify(self, char: BleakGATTCharacteristic, data: bytearray) -> None:
        raw = bytes(data)
        if len(raw) < 4 or raw[0:2] != b"@+":
            return
        cmd = chr(raw[2])
        payload = raw[3:-1] if raw[-1] == 0x25 else raw[3:]

        if cmd == "V":
            try:
                vol = raw_to_display(int(payload))
                self.call_from_thread(self._apply_volume, vol)
            except ValueError:
                pass
        elif cmd == "M":
            self.call_from_thread(self._apply_mute, payload == b"11")
        elif cmd == "I":
            if len(payload) >= 2:
                name = INPUT_NAMES.get(payload[1], chr(payload[1]))
                self.call_from_thread(self._apply_input, name)
        elif cmd == "A":
            state = "on" if payload == b"11" else "off"
            self.call_from_thread(self._log, f"av-direct: {state}")

    def _apply_volume(self, vol: int) -> None:
        self.volume = vol
        self._log(f"volume: {vol}/75")

    def _apply_mute(self, muted: bool) -> None:
        self.muted = muted
        self._log(f"mute: {'on' if muted else 'off'}")

    def _apply_input(self, name: str) -> None:
        self._known_input = name
        try:
            self.query_one("#input_select", Select).value = name
        except Exception:
            pass
        self._log(f"input: {name}")

    def watch_volume(self, vol: int) -> None:
        self.query_one("#vol_bar", ProgressBar).progress = vol
        self.query_one("#vol_label", Label).update(f"Volume: {vol}/75")

    def watch_muted(self, muted: bool) -> None:
        btn = self.query_one("#mute_btn", Button)
        btn.variant = "warning" if muted else "default"
        btn.label = "Unmute" if muted else "Mute"

    def _log(self, msg: str) -> None:
        self.query_one("#log", RichLog).write(msg)

    async def _send(self, data: bytes) -> None:
        client = self._client
        if client is None or not client.is_connected:
            self._log("[red]Not connected.[/]")
            return
        try:
            await client.write_gatt_char(DATA_CHAR_UUID, data, response=True)
        except Exception as e:
            self._log(f"[red]Send error: {e}[/]")

    async def action_volume_up(self) -> None:
        new_vol = min(VOL_MAX, self.volume + 1)
        await self._send(b"@+V2" + f"{new_vol:02d}".encode() + b"%")

    async def action_volume_down(self) -> None:
        new_vol = max(VOL_MIN, self.volume - 1)
        await self._send(b"@+V2" + f"{new_vol:02d}".encode() + b"%")

    async def action_toggle_mute(self) -> None:
        await self._send(b"@+M10%" if self.muted else b"@+M11%")

    async def action_fetch_status(self) -> None:
        client = self._client
        if client is None or not client.is_connected:
            self._log("[red]Not connected.[/]")
            return
        for letter in b"VMIA":
            await client.write_gatt_char(
                DATA_CHAR_UUID, b"@+F1" + bytes([letter]) + b"%", response=True
            )
            await asyncio.sleep(0.15)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "mute_btn":
            await self.action_toggle_mute()

    async def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "input_select":
            return
        if event.value is Select.BLANK:
            return
        if event.value == self._known_input:
            return  # programmatic update from notification, not user input
        await self._send(b"@+I1" + INPUTS[str(event.value)] + b"%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cyrus ONE BLE remote TUI")
    parser.add_argument("-a", "--address", default=DEFAULT_ADDRESS,
                        help=f"BT address (default: {DEFAULT_ADDRESS})")
    parser.add_argument("--adapter", default=DEFAULT_ADAPTER,
                        help=f"HCI adapter (default: {DEFAULT_ADAPTER})")
    args = parser.parse_args()
    CyrusApp(args.address, args.adapter).run()
