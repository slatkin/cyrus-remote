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
                ? `${vol}/75  ${input}${muted ? "  muted" : ""}`
                : "cyrus"
            color: connected ? Color.mOnSurface : Color.mOnSurfaceVariant
            pointSize: Style.fontSizeS
        }
    }

    MouseArea {
        anchors.fill: parent
        enabled: connected
        onClicked: {
            if (!muteProc.running) {
                muteProc.command = ["cyrus-cmd", muted ? "unmute" : "mute"]
                muteProc.running = true
            }
        }
        onWheel: function(wheel) {
            volProc.running = false
            volProc.command = ["cyrus-cmd", wheel.angleDelta.y > 0 ? "vol+" : "vol-"]
            volProc.running = true
        }
    }

    Process { id: muteProc; running: false }
    Process { id: volProc;  running: false }
}
