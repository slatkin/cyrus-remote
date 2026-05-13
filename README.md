# cyrus-remote

Python tools for controlling the **Cyrus ONE** integrated amplifier over Bluetooth Low Energy, replacing the official Android/iOS app.

## Components

| File | Purpose |
|------|---------|
| `cyrus.py` | Interactive REPL with persistent status bar |
| `cyrus_daemon.py` | Headless BLE daemon that feeds the Noctalia bar widget |
| `cyrus_cmd.py` | One-shot command sender (used by the widget) |
| `plugin/` | Noctalia shell plugin (bar widget) |

## Requirements

- Python 3.10+
- [`bleak`](https://github.com/hbldh/bleak) — BLE library
- [`prompt_toolkit`](https://github.com/prompt-toolkit/python-prompt-toolkit) — status bar in REPL
- Linux with BlueZ; two adapters supported via `--adapter`

```
pip install bleak prompt_toolkit
```

## Install

```
make install
```

Installs `cyrus-remote` (REPL), `cyrus-daemon`, and `cyrus-cmd` to `~/.local/bin`, and copies the Noctalia plugin to `~/.config/noctalia/plugins/cyrus-remote/`.

The `cr` alias is also created for `cyrus-remote`.

After installing, add the plugin to `~/.config/noctalia/plugins.json`:

```json
{ "id": "cyrus-remote", "enabled": true, "path": "/home/you/.config/noctalia/plugins/cyrus-remote" }
```

## REPL usage

```
cyrus-remote          # or: cr
```

Connects to the amp and drops into an interactive prompt with a live status bar at the bottom:

```
Connected to ONE-888. Type 'help' for commands, 'quit' to exit.

  volume: 49/75
  input: optical
>
 vol: 49/75  |  input: optical  |  mute: off
```

The status bar updates live from BLE notifications. Command history persists across sessions in `$XDG_STATE_HOME/cyrus-remote/history`.

To specify a different BT address or adapter:

```
cyrus-remote -a AA:BB:CC:DD:EE:FF --adapter hci1
```

### Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `mute` | `m` | Mute |
| `unmute` | `um` | Unmute |
| `volume <0-75>` | `vol`, `v` | Set volume |
| `input <name>` | `i` | Switch input source |
| `status` | `s` | Refresh status bar from device |
| `help` | `?`, `h` | List commands |
| `quit` | `q`, `exit` | Disconnect and exit |

### Input sources

| Name | Physical input |
|------|---------------|
| `bt` | Bluetooth |
| `usb` | USB-B |
| `optical` | Optical / TOSLINK |
| `spdif` | S/PDIF coax |
| `phono` | Phono |
| `aux5` | Aux 5 |
| `aux6` | Aux 6 |
| `av` | AV |

## Noctalia bar widget

Run the daemon in the background — it handles BLE and pushes state to the widget via Quickshell IPC:

```
cyrus-daemon &
```

The widget shows `vol / input` in the bar and updates on every BLE notification from the amp. Click to toggle mute; scroll to adjust volume.

The daemon auto-reconnects if the link drops and marks the widget as disconnected in the meantime.

## Multiple Bluetooth adapters

Both tools default to `hci0`. Pass `--adapter hciN` to choose a different adapter:

```
cyrus-remote --adapter hci1
cyrus-daemon  --adapter hci1
```

## Finding your device address

If you don't know your amp's Bluetooth address:

```python
python3 - <<'EOF'
import asyncio
from bleak import BleakScanner

SERVICE_UUID = "bc2f4cc6-aaef-4351-9034-d66268e328f0"

async def main():
    devices = await BleakScanner.discover(timeout=15.0, return_adv=True)
    for d, adv in devices.values():
        if SERVICE_UUID.lower() in [str(u).lower() for u in adv.service_uuids]:
            print(f"{d.address}  {d.name}")

asyncio.run(main())
EOF
```

The amp advertises as `ONE-888` or similar.

## How it works

The Cyrus ONE uses a **MelodySmart** BLE-to-UART bridge (Blue Creation / Dialog Semiconductor). All communication goes through a single GATT characteristic that is both writable and notifiable:

| Role | UUID |
|------|------|
| Service | `bc2f4cc6-aaef-4351-9034-d66268e328f0` |
| Data characteristic | `06d1e5e7-79ad-4a71-8faa-373789f7d93c` |

### Wire format

```
@+  <CMD>  1  <data...>  %
```

- `@+` — fixed prefix (`0x40 0x2B`)
- `CMD` — ASCII command letter
- `1` — fixed subcommand byte (`0x31`), required on every write
- `data` — ASCII payload
- `%` — end byte (`0x25`)

The device echoes commands back as notifications and sends unsolicited updates when physical controls are used.

### Command reference

| Action | Bytes |
|--------|-------|
| Mute on | `@+M11%` |
| Mute off | `@+M10%` |
| Set volume (step N, zero-padded) | `@+V2<NN>%` |
| Switch input (1–8) | `@+I1<N>%` |
| Fetch volume / mute / input | `@+F1V%` / `@+F1M%` / `@+F1I%` |

Volume steps 0–75 map to raw values 0–1000 via a non-linear (log-taper) lookup table matching the amp's physical knob feel.

### Reverse engineering

Protocol recovered by decompiling `Cyrus ONE Remote_1.4_APKPure.apk` with [androguard](https://github.com/androguard/androguard), tracing `fill-array-data-payload` literals in `MainControlActivity` and `CyrusONEModel`, and decoding the DEX static-values section of the `Const` class.

The critical detail: the fixed `1` byte at position 3 of every command — without it the amp silently ignores all writes.
