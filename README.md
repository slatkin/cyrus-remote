# cyrus-remote

A Python CLI for controlling the **Cyrus ONE** integrated amplifier over Bluetooth Low Energy, replacing the official Android/iOS app.

## Requirements

- Python 3.10+
- [`bleak`](https://github.com/hbldh/bleak) BLE library
- Linux with BlueZ (tested), macOS should also work

```
pip install bleak
```

## Usage

```
python3 cyrus.py
```

The script connects to the amplifier (hardcoded address `FD:6D:51:B8:5F:7E` — change `DEFAULT_ADDRESS` in the script to match your unit), prints the current state, and drops into an interactive prompt:

```
Scanning for FD:6D:51:B8:5F:7E…
Found: ONE-888 (FD:6D:51:B8:5F:7E)
Connected to ONE-888. Type 'help' for commands, 'quit' to exit.

  volume: 49/75  (raw 254)
  mute: off
  input: usb
  av-direct: off
>
```

The connection is held open for the entire session. If the link drops the script reconnects automatically.

To use a different address without editing the file:

```
python3 cyrus.py -a AA:BB:CC:DD:EE:FF
```

## Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `mute` | `m` | Mute audio output |
| `unmute` | `um` | Unmute audio output |
| `volume <0-75>` | `vol`, `v` | Set volume (display steps 0–75) |
| `input <name>` | `i` | Switch input source (see table below) |
| `status` | `s` | Print current volume, mute state, input, and AV direct |
| `help` | `?`, `h` | List commands |
| `quit` | `q`, `exit` | Disconnect and exit |

### Input sources

| Name | Source |
|------|--------|
| `bt` | Bluetooth |
| `usb` | USB-B |
| `optical` | Optical / TOSLINK |
| `spdif` | S/PDIF coax |
| `phono` | Phono |
| `aux6` | Aux 6 |
| `aux7` | Aux 7 |
| `av` | AV |

## Finding your device address

If you don't know your amplifier's Bluetooth address, run a one-off scan:

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

The amplifier advertises with names like `ONE-888` or `CyrusONE-52888`.

## How it works

The Cyrus ONE uses a **MelodySmart** BLE-to-UART bridge module (Blue Creation / Dialog Semiconductor). All communication goes through a single GATT characteristic that is both writable and notifiable:

| Role | UUID |
|------|------|
| Service | `bc2f4cc6-aaef-4351-9034-d66268e328f0` |
| Data characteristic (write + notify) | `06d1e5e7-79ad-4a71-8faa-373789f7d93c` |

### Wire format

Every message is framed as:

```
@+  <CMD>  1  <data...>  %
```

- `@+` — fixed 2-byte prefix (`0x40 0x2B`)
- `CMD` — ASCII command letter
- `1` — fixed subcommand byte (`0x31`), present in every command
- `data` — command-specific payload (ASCII digits or letters)
- `%` — end byte (`0x25`)

The device echoes each command back as a notification, and also sends unsolicited state updates when the physical controls are used (e.g. turning the volume knob).

### Command reference

| Action | Bytes sent |
|--------|-----------|
| Mute on | `@+M11%` |
| Mute off | `@+M10%` |
| Set volume (step N) | `@+V2<NN>%` — N zero-padded to 2 digits |
| Switch input | `@+I1<N>%` — N is `1`–`8` |
| Fetch volume | `@+F1V%` |
| Fetch mute | `@+F1M%` |
| Fetch input | `@+F1I%` |
| Fetch AV direct | `@+F1A%` |

Volume steps 0–75 are a display scale. The amplifier reports raw values 0–1000; the app's `generateMap()` lookup table maps them to display steps.

### Reverse engineering

The protocol was recovered by decompiling `Cyrus ONE Remote_1.4_APKPure.apk` with [androguard](https://github.com/androguard/androguard), tracing `fill-array-data-payload` literals in `MainControlActivity` and `CyrusONEModel`, and decoding the DEX static-values section of the `Const` class for byte constants.

The critical discovery was the fixed `1` byte at position 3 of every command (e.g. `M11%` not `M1%`) — without it the amplifier silently ignores all writes.
