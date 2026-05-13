# cyrus-remote

Python tools for controlling the **Cyrus ONE** integrated amplifier over Bluetooth Low Energy, replacing the official Android/iOS app.

![Red panda](https://potterparkzoo.org/wp-content/uploads/2025/08/4204-scaled.jpg)

## Architecture

BLE only allows one connection at a time. The recommended setup is a **server/client model**: a small headless machine (Pi, NUC, Proxmox host, etc.) near the amp holds the single BLE connection, and every desktop/laptop connects to it as a client.

```
[ Cyrus ONE amp ]
       │ BLE
[ server running cyrus-daemon --no-ipc ]
       │ TCP :9876
  ┌────┴────┐
  │         │
[ desktop ] [ laptop ]
cyrus-proxy  cyrus-proxy
  │               │
Noctalia       Noctalia
bar widget     bar widget
```

Each client machine runs `cyrus-proxy`, which:
- Receives live state pushes from the daemon (volume, mute, input) and feeds them to the local Noctalia bar widget via IPC
- Forwards commands from the local bar widget (vol+/-, mute, input switch) back to the daemon over TCP

## Components

| File | Purpose |
|------|---------|
| `cyrus_daemon.py` | BLE daemon — connects to amp, serves Unix socket + TCP |
| `cyrus_proxy.py` | Client proxy — relays state and commands between daemon and local Noctalia |
| `cyrus_cmd.py` | One-shot command sender (used by the bar widget) |
| `cyrus.py` | Interactive REPL (optional, for direct local use) |
| `plugin/` | Noctalia shell plugin (bar widget + IPC handler) |

## Server setup

### Requirements (server)

- Linux with BlueZ
- Python 3.10+
- `bleak`: `pip install bleak`

### Install

```bash
git clone https://github.com/slatkin/cyrus-remote
cd cyrus-remote
sudo make install-service
sudo systemctl start cyrus-daemon
```

`install-service` copies `cyrus-daemon` to `/usr/local/bin`, installs the systemd unit to `/etc/systemd/system/`, and enables it on boot.

The service runs with `--no-ipc` by default (no Noctalia on the server) and binds TCP port **9876**.

### Verify

```bash
sudo systemctl status cyrus-daemon
sudo journalctl -u cyrus-daemon -f
```

You should see `Scanning for …` then `Connected to ONE-xxx` once the amp is on.

## Client setup (desktop / laptop)

### Requirements

- Python 3.10+, `bleak`: `pip install bleak`
- [Noctalia](https://github.com/noctalia-dev/noctalia) shell

### Install

```bash
git clone https://github.com/slatkin/cyrus-remote
cd cyrus-remote
make install
```

Installs `cyrus-proxy`, `cyrus-cmd`, and the Noctalia plugin to `~/.local/bin` and `~/.config/noctalia/plugins/cyrus-remote/`.

### Configure

Set `CYRUS_PROXY_HOST` to the server's IP or hostname. In fish:

```fish
set -Ux CYRUS_PROXY_HOST 192.168.1.x
```

In bash/zsh (add to your profile):

```bash
export CYRUS_PROXY_HOST=192.168.1.x
```

Then add the plugin to `~/.config/noctalia/plugins.json`:

```json
"states": {
    "cyrus-remote": { "enabled": true }
}
```

Restart Noctalia. The plugin detects `CYRUS_PROXY_HOST` and auto-starts `cyrus-proxy` instead of a local daemon.

### Firewall

Open port 9876/TCP on the server if needed:

```bash
# ufw
ufw allow 9876/tcp
```

## Single-machine setup

If the amp is always near your desktop and you don't need the server model, skip `cyrus-proxy` and run the daemon locally without `--no-ipc`:

```bash
cyrus-daemon &
```

Leave `CYRUS_PROXY_HOST` unset. The plugin auto-starts the daemon and pushes state via local Noctalia IPC.

## Bar widget

The Noctalia bar widget shows volume % and input source. Updates arrive as live BLE notifications — no polling.

- **Left click** — toggle mute
- **Right click** — input source menu
- **Scroll wheel** — volume up/down (throttled to one step per 300 ms)

## REPL (optional)

For direct interactive control without the widget:

```bash
cyrus-remote          # or: cr
```

```
Connected to ONE-888. Type 'help' for commands, 'quit' to exit.

> help
  commands: mute  unmute  volume <0-90>  input <bt|usb|optical|spdif|phono|aux5|aux6>  status  quit
>
 vol: 80%  |  input: optical  |  mute: off
```

The status bar updates live from BLE notifications. Command history persists in `$XDG_STATE_HOME/cyrus-remote/history`.

### Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `mute` | `m` | Mute |
| `unmute` | `um` | Unmute |
| `volume <0-90>` | `vol`, `v` | Set volume step |
| `input <name>` | `i` | Switch input source |
| `status` | `s` | Refresh all state from device |
| `quit` | `q`, `exit` | Disconnect and exit |

## Graceful shutdown

The daemon handles SIGTERM cleanly — it disconnects BLE before exiting, so you don't need to restart Bluetooth:

```bash
pkill cyrus-daemon
```

Do not use `kill -9` (SIGKILL cannot be caught and will leave the BLE connection open).

## Finding your device address

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

The amp advertises as `ONE-888` or similar. Pass a custom address with `-a AA:BB:CC:DD:EE:FF`.

## How it works

The Cyrus ONE uses a **MelodySmart** BLE-to-UART bridge (Blue Creation / Dialog Semiconductor). All communication goes through a single GATT characteristic:

| Role | UUID |
|------|------|
| Service | `bc2f4cc6-aaef-4351-9034-d66268e328f0` |
| Data characteristic | `06d1e5e7-79ad-4a71-8faa-373789f7d93c` |

### Wire format

```
@+  <CMD>  <subtype>  <data...>  %
```

| Action | Bytes |
|--------|-------|
| Mute on | `@+M11%` |
| Mute off | `@+M10%` |
| Set volume (step 0–90) | `@+V2<NN>%` |
| Switch input (1–8) | `@+I1<N>%` |
| Fetch volume / mute / input | `@+F1V%` / `@+F1M%` / `@+F1I%` |

The amp echoes commands back as notifications and sends unsolicited updates when physical controls are used. Volume steps 0–90 map linearly to 0–100%.

### Reverse engineering

Protocol recovered by decompiling `Cyrus ONE Remote_1.4_APKPure.apk` with [androguard](https://github.com/androguard/androguard), tracing `fill-array-data-payload` literals in `MainControlActivity` and `CyrusONEModel`, and decoding the DEX static-values section of the `Const` class.
