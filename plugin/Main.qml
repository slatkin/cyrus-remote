import QtQuick
import Quickshell

Item {
    id: root
    property var pluginApi: null

    property bool connected: false
    property int vol: 0
    property bool muted: false
    property string inputName: "--"

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
