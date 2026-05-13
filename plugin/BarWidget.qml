import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Widgets

Rectangle {
    id: root
    property var pluginApi: null
    property ShellScreen screen
    property string widgetId: ""
    property string section: ""
    property int sectionWidgetIndex: -1
    property int sectionWidgetsCount: 0

    readonly property var amp:        pluginApi?.mainInstance
    readonly property bool connected: amp?.connected  ?? false
    readonly property int  vol:       amp?.vol        ?? 0
    readonly property bool muted:     amp?.muted      ?? false
    readonly property string input:   amp?.inputName  ?? "--"

    implicitWidth:  row.implicitWidth + Style.marginM * 2
    implicitHeight: Style.barHeight
    color:          Style.capsuleColor
    radius:         Style.radiusM

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: Style.marginS

        NIcon {
            icon:  connected ? "music" : "bluetooth-off"
            color: connected ? Color.mPrimary : Color.mOnSurfaceVariant
        }

        NText {
            text: connected
                ? `${Math.round(vol * 100 / 75)}%  ${input}${muted ? "  muted" : ""}`
                : "cyrus"
            color: connected ? Color.mOnSurface : Color.mOnSurfaceVariant
            pointSize: Style.fontSizeS
        }
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        enabled: connected
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: function(mouse) {
            if (mouse.button === Qt.RightButton) {
                inputMenu.openAtItem(root, screen)
            } else {
                if (!muteProc.running) {
                    muteProc.command = ["cyrus-cmd", muted ? "unmute" : "mute"]
                    muteProc.running = true
                }
            }
        }
        onWheel: function(wheel) {
            if (wheel.angleDelta.y > 0) {
                if (!volUpProc.running)   volUpProc.running   = true
            } else {
                if (!volDownProc.running) volDownProc.running = true
            }
        }
    }

    NPopupContextMenu {
        id: inputMenu
        model: {
            const a = root.input
            return [
                { label: (a === "bt"      ? "✓ " : "") + "Bluetooth", action: "bt",      icon: "bluetooth"  },
                { label: (a === "usb"     ? "✓ " : "") + "USB",       action: "usb",     icon: "device-usb" },
                { label: (a === "optical" ? "✓ " : "") + "Optical",   action: "optical", icon: "music"      },
                { label: (a === "spdif"   ? "✓ " : "") + "SPDIF",     action: "spdif",   icon: "music"      },
                { label: (a === "phono"   ? "✓ " : "") + "Phono",     action: "phono",   icon: "vinyl"      },
                { label: (a === "aux5"    ? "✓ " : "") + "Aux 5",     action: "aux5",    icon: "plug"       },
                { label: (a === "aux6"    ? "✓ " : "") + "Aux 6",     action: "aux6",    icon: "plug"       },
            ]
        }
        onTriggered: function(action) {
            inputMenu.close()
            inputProc.command = ["cyrus-cmd", "input:" + action]
            if (!inputProc.running) inputProc.running = true
        }
    }

    Process { id: muteProc;    running: false }
    Process { id: volUpProc;   command: ["cyrus-cmd", "vol+"]; running: false }
    Process { id: volDownProc; command: ["cyrus-cmd", "vol-"]; running: false }
    Process { id: inputProc;   running: false }
}
