import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: root
    property var pluginApi: null

    property bool connected: false
    property int vol: 0
    property int volPct: 0
    property bool muted: false
    property string inputName: "--"

    // Auto-start daemon (local) or proxy (remote). Set CYRUS_PROXY_HOST to use proxy mode.
    Process {
        command: ["sh", "-c",
            "P=\"$CYRUS_PROXY_HOST\"; " +
            "if [ -n \"$P\" ]; then " +
            "  pgrep -f cyrus-proxy | grep -q python || $HOME/.local/bin/cyrus-proxy --host \"$P\"; " +
            "else " +
            "  pgrep -f cyrus-daemon | grep -q python || $HOME/.local/bin/cyrus-daemon; " +
            "fi"]
        running: true
    }

    IpcHandler {
        target: "plugin:cyrus-remote"

        function updateState(data: string) {
            try {
                const s = JSON.parse(data)
                root.connected  = s.connected ?? false
                root.vol        = s.vol       ?? 0
                root.volPct     = s.vol_pct   ?? 0
                root.muted      = s.muted     ?? false
                root.inputName  = s.input     ?? "--"
            } catch(e) {}
        }
    }
}
