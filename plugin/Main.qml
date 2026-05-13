import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: root
    property var pluginApi: null

    property bool connected: false
    property int vol: 0
    property bool muted: false
    property string inputName: "--"

    // Auto-start the daemon when the plugin loads; guard against double-start
    Process {
        command: ["sh", "-c", "pgrep -f cyrus-daemon | grep python > /dev/null || $HOME/.local/bin/cyrus-daemon"]
        running: true
    }

    IpcHandler {
        target: "plugin:cyrus-remote"

        function updateState(data: string) {
            try {
                const s = JSON.parse(data)
                root.connected  = s.connected ?? false
                root.vol        = s.vol       ?? 0
                root.muted      = s.muted     ?? false
                root.inputName  = s.input     ?? "--"
            } catch(e) {}
        }
    }
}
