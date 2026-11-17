import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore

// Pomodoro timer. State lives in ~/.local/share/summit/focus.json, which Shika's
// floating mini-timer reads too: "Pop out" puts it on top of every app.
PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation

    readonly property var focusChoices: [25, 45, 60, 15]
    property int choice: 0
    property string mode: "focus"               // "focus" | "break"
    property bool running: false
    property double endsAt: 0                   // ms timestamp while running
    property double leftMs: focusChoices[0] * 60000
    property double now: Date.now()
    property int sessions: 0
    property bool popout: false
    property double updated: 0
    property bool loaded: false
    readonly property double total: (mode === "focus" ? focusChoices[choice]
                                     : (sessions > 0 && sessions % 4 === 0 ? 15 : 5)) * 60000
    readonly property double remaining: running ? Math.max(0, endsAt - now) : leftMs
    readonly property real progress: 1 - remaining / total

    Theme { id: theme }
    Store { id: store }

    function fmt(ms) {
        var s = Math.ceil(ms / 1000), m = Math.floor(s / 60)
        s = s % 60
        return m + ":" + (s < 10 ? "0" : "") + s
    }
    function persist() {
        updated = Date.now()
        store.run("set focus " + store.json({
            mode: mode, running: running, endsAt: endsAt, leftMs: leftMs, total: total,
            sessions: sessions, choice: choice, popout: popout, updated: updated }))
    }
    function apply(d) {
        if (!d || !d.updated || d.updated <= updated) return
        mode = d.mode || "focus"; choice = d.choice || 0; sessions = d.sessions || 0
        endsAt = d.endsAt || 0; running = !!d.running; popout = !!d.popout
        leftMs = d.leftMs || total
        updated = d.updated
        now = Date.now()
    }
    function toggle() {
        if (running) { leftMs = remaining; running = false }
        else { endsAt = Date.now() + leftMs; now = Date.now(); running = true }
        persist()
    }
    function reset() { running = false; leftMs = total; persist() }
    function switchTo(m) { mode = m; running = false; leftMs = total; persist() }
    function finish() {
        running = false
        if (mode === "focus") {
            sessions += 1
            store.run("notify " + store.enc("Focus done 🎯") + " " + store.enc("Nice work. Take a short break."))
            switchTo("break")
        } else {
            store.run("notify " + store.enc("Break over") + " " + store.enc("Back to the climb."))
            switchTo("focus")
        }
    }

    Component.onCompleted: store.get("focus", function (d) {
        root.apply(d)
        root.loaded = true
        if (root.running && root.endsAt <= Date.now()) root.finish()
    })
    Timer {   // pick up pause/resume/close from the floating timer
        interval: 1500; repeat: true; running: root.loaded
        onTriggered: store.get("focus", root.apply)
    }
    Timer {
        interval: 250; repeat: true; running: root.running
        onTriggered: { root.now = Date.now(); if (root.remaining <= 0) root.finish() }
    }

    fullRepresentation: GlassCard {
        Layout.preferredWidth: 300
        Layout.preferredHeight: 132
        Layout.minimumWidth: 260
        Layout.minimumHeight: 120

        RowLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 16

            Item {
                Layout.preferredWidth: 96
                Layout.preferredHeight: 96
                Layout.alignment: Qt.AlignVCenter
                Shape {
                    anchors.fill: parent
                    layer.enabled: true
                    layer.samples: 4
                    ShapePath {
                        strokeColor: theme.line; strokeWidth: 5; fillColor: "transparent"
                        PathAngleArc { centerX: 48; centerY: 48; radiusX: 42; radiusY: 42; startAngle: 0; sweepAngle: 360 }
                    }
                    ShapePath {
                        strokeColor: root.mode === "focus" ? theme.red : theme.text
                        strokeWidth: 5; fillColor: "transparent"; capStyle: ShapePath.RoundCap
                        PathAngleArc {
                            centerX: 48; centerY: 48; radiusX: 42; radiusY: 42
                            startAngle: -90; sweepAngle: 360 * Math.max(0.002, root.progress)
                        }
                    }
                }
                Text {
                    anchors.centerIn: parent
                    text: root.fmt(root.remaining)
                    color: theme.text
                    font.family: theme.font
                    font.pixelSize: 20
                    font.weight: Font.DemiBold
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8
                Header {
                    Layout.fillWidth: true
                    title: root.mode === "focus" ? "Focus" : "Break"
                }
                Row {
                    spacing: 5
                    Repeater {
                        model: 4
                        Rectangle {
                            required property int index
                            width: 7; height: 7; radius: 3.5
                            color: index < root.sessions % 4 || (root.sessions > 0 && root.sessions % 4 === 0)
                                   ? theme.red : theme.line
                        }
                    }
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: 6
                    Chip { label: root.running ? "Pause" : "Start"; active: root.running; onClicked: root.toggle() }
                    Chip { label: "Reset"; onClicked: root.reset() }
                    Chip {
                        label: root.mode === "focus" ? root.focusChoices[root.choice] + " min" : "Skip"
                        onClicked: {
                            if (root.mode === "break") { root.switchTo("focus"); return }
                            root.choice = (root.choice + 1) % root.focusChoices.length
                            root.reset()
                        }
                    }
                    Chip {
                        label: root.popout ? "⧉ Floating" : "⧉ Pop out"
                        active: root.popout
                        onClicked: {
                            root.popout = !root.popout
                            root.persist()
                            if (root.popout) store.run("launch-shika")   // no-op if he's already running
                        }
                    }
                }
            }
        }
    }
}
