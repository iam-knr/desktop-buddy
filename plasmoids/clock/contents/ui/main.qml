import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore

// Summit Clock: the time set like the wallpaper quote (tall condensed caps, red accent),
// the date in spaced capitals like "— NIMSDAI", and the next thing Shika will bark about.
// Hover it for three small toggles: glass card, 24-hour time, next reminder.
PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation

    property date now: new Date()
    property var next: null
    property int openTasks: 0
    property bool shika: true
    readonly property bool glass: Plasmoid.configuration.glass
    readonly property bool hour24: Plasmoid.configuration.hour24
    readonly property bool showNext: Plasmoid.configuration.showNext
    readonly property string display: {
        var want = ["Bebas Neue", "BebasNeue", "Oswald", "Anton", "League Gothic", "Fjalla One",
                    "Noto Sans Display Condensed", "Ubuntu Condensed", "DejaVu Sans Condensed"]
        var have = Qt.fontFamilies()
        for (var i = 0; i < want.length; i++)
            if (have.indexOf(want[i]) >= 0) return want[i]
        return "Noto Sans"
    }
    readonly property bool condensed: display !== "Noto Sans"
    readonly property bool inPanel: Plasmoid.formFactor === PlasmaCore.Types.Horizontal
                                    || Plasmoid.formFactor === PlasmaCore.Types.Vertical
    readonly property string dayText: Qt.formatDate(now, "dddd  ·  d").toUpperCase()

    Theme { id: theme }
    Store { id: store }

    function hh() {
        var h = now.getHours()
        if (!hour24) { h = h % 12; if (h === 0) h = 12 }
        return hour24 && h < 10 ? "0" + h : String(h)
    }
    function mm() { var m = now.getMinutes(); return (m < 10 ? "0" : "") + m }
    function load() {
        store.get("items", function (d) {
            var items = d.items || []
            var timed = items.filter(function (t) { return t.due && !t.done })
                             .sort(function (a, b) { return a.due - b.due })
            root.next = timed.length ? timed[0] : null
            root.openTasks = items.filter(function (t) { return t.kind === "task" && !t.done }).length
            root.shika = d.shika
        })
    }
    function when(due) {
        var diff = due - now.getTime() / 1000
        if (diff < 0) return "now"
        if (diff < 3600) return "in " + Math.max(1, Math.round(diff / 60)) + " min"
        var d = new Date(due * 1000), t = Qt.formatTime(d, hour24 ? "HH:mm" : "h:mm AP")
        if (d.toDateString() === now.toDateString()) return t
        var tm = new Date(now.getTime() + 86400000)
        if (d.toDateString() === tm.toDateString()) return "tmrw " + t
        return Qt.formatDate(d, "ddd d MMM") + " · " + t
    }

    Timer {                       // tick on the minute boundary, cheap on the CPU
        interval: 1000; running: true; repeat: true
        onTriggered: { var n = new Date(); if (n.getMinutes() !== root.now.getMinutes() || n.getDate() !== root.now.getDate()) root.now = n }
    }
    Timer { interval: 15000; running: root.showNext; repeat: true; triggeredOnStart: true; onTriggered: root.load() }
    Timer { interval: 30000; running: true; repeat: true; onTriggered: root.now = new Date() }

    fullRepresentation: Item {
        id: face
        // On the desktop it scales with the widget; in a panel it fills the panel height on one line.
        Layout.preferredWidth: root.inPanel ? timeRow.implicitWidth + 12 : 420
        Layout.preferredHeight: root.inPanel ? -1 : (root.showNext ? 200 : 170)
        Layout.minimumWidth: root.inPanel ? timeRow.implicitWidth + 12 : 240
        Layout.minimumHeight: root.inPanel ? -1 : 130
        Layout.fillHeight: root.inPanel
        readonly property real k: Math.min(width / 420, height / (root.showNext ? 200 : 170))
        readonly property real timeSize: root.inPanel ? Math.max(12, height * 0.72)
                                                      : (root.condensed ? 128 : 100) * k

        HoverHandler { id: hover }

        GlassCard {
            anchors.fill: parent
            visible: root.glass
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: root.inPanel ? 0 : (root.glass ? 20 * face.k : 4)
            spacing: 2 * face.k

            Row {
                id: timeRow
                spacing: 0
                Layout.alignment: root.inPanel ? Qt.AlignVCenter : Qt.AlignLeft
                Text {
                    id: hours
                    text: root.hh()
                    color: theme.text
                    font.family: root.display
                    font.pixelSize: face.timeSize
                    font.weight: root.condensed ? Font.Normal : Font.Black
                    style: Text.Raised
                    styleColor: Qt.rgba(0, 0, 0, 0.55)
                }
                Text {
                    text: ":"
                    color: theme.red
                    font.family: root.display
                    font.pixelSize: hours.font.pixelSize
                    font.weight: hours.font.weight
                }
                Text {
                    text: root.mm()
                    color: theme.text
                    font.family: root.display
                    font.pixelSize: hours.font.pixelSize
                    font.weight: hours.font.weight
                    style: Text.Raised
                    styleColor: Qt.rgba(0, 0, 0, 0.55)
                }
                Text {                       // AM/PM, same size as the digits
                    visible: !root.hour24
                    text: root.now.getHours() < 12 ? "AM" : "PM"
                    color: theme.red
                    font.family: root.display
                    font.pixelSize: hours.font.pixelSize
                    font.weight: hours.font.weight
                    anchors.baseline: hours.baseline
                    leftPadding: hours.font.pixelSize * 0.14
                    style: Text.Raised
                    styleColor: Qt.rgba(0, 0, 0, 0.55)
                }
                Text {                       // in a panel the day sits on the same line
                    visible: root.inPanel
                    text: root.dayText
                    color: theme.text
                    opacity: 0.8
                    font.family: theme.font
                    font.pixelSize: Math.max(10, hours.font.pixelSize * 0.36)
                    font.letterSpacing: 3
                    font.weight: Font.DemiBold
                    anchors.verticalCenter: hours.verticalCenter
                    leftPadding: hours.font.pixelSize * 0.35
                }
            }

            RowLayout {
                visible: !root.inPanel
                spacing: 10 * face.k
                Rectangle { Layout.preferredWidth: 18 * face.k; height: 1.5; color: theme.text; opacity: 0.8 }
                Text {
                    text: root.dayText
                    color: theme.text
                    opacity: 0.85
                    font.family: theme.font
                    font.pixelSize: Math.max(11, 15 * face.k)
                    font.letterSpacing: 5 * face.k
                    font.weight: Font.DemiBold
                }
            }

            RowLayout {
                visible: root.showNext && !root.inPanel
                Layout.topMargin: 8 * face.k
                spacing: 8 * face.k
                Rectangle {
                    width: 6 * face.k; height: width; radius: width / 2
                    color: root.next && root.next.due - root.now.getTime() / 1000 < 900 ? theme.red : theme.muted
                }
                Text {
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    color: !root.shika ? theme.red : theme.muted
                    font.family: theme.font
                    font.pixelSize: Math.max(11, 13 * face.k)
                    text: !root.shika ? "Shika is asleep, so nothing will bark"
                        : root.next ? "NEXT   " + root.next.text + "  ·  " + root.when(root.next.due)
                        : (root.openTasks ? root.openTasks + (root.openTasks === 1 ? " task" : " tasks") + " open, nothing timed"
                                          : "Nothing due. Keep climbing.")
                }
            }
            Item { Layout.fillHeight: true; visible: !root.inPanel }
        }

        Row {                        // hover toggles, top-right corner
            visible: !root.inPanel
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.margins: 6
            spacing: 4
            opacity: hover.hovered ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 160 } }
            Chip {
                label: "Glass"
                active: root.glass
                onClicked: Plasmoid.configuration.glass = !root.glass
            }
            Chip {
                label: "24h"
                active: root.hour24
                onClicked: Plasmoid.configuration.hour24 = !root.hour24
            }
            Chip {
                label: "Next"
                active: root.showNext
                onClicked: Plasmoid.configuration.showNext = !root.showNext
            }
        }
    }
}
