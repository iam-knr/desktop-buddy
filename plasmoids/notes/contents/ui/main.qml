import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore

// One sticky note per widget. Text is written to ~/.local/share/summit/notes.json
// 0.6 s after you stop typing (fsync'd), so restarts and crashes keep it, and is
// mirrored into the Shika app. Erasing (bin, twice) keeps the text there as a version.
PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation

    readonly property string key: "note-" + Plasmoid.id
    property string body: ""
    property int tint: 0
    property bool loaded: false
    property bool confirmDelete: false
    readonly property var tints: [
        { name: "Smoke", fill: Qt.rgba(0.035, 0.035, 0.045, 0.62), dot: "#8a8a90" },
        { name: "Ember", fill: Qt.rgba(0.20, 0.03, 0.05, 0.55), dot: "#E11D2E" },
        { name: "Frost", fill: Qt.rgba(0.85, 0.87, 0.92, 0.14), dot: "#F2F2F3" }]

    Theme { id: theme }
    Store { id: store }

    function persist() {
        if (!loaded) return
        store.run("note-set " + store.enc(key) + " " + store.json({ text: body, tint: tint }))
    }

    Component.onCompleted: store.get("notes", function (d) {
        var n = d[root.key]
        if (n) { root.body = n.text || ""; root.tint = n.tint || 0 }
        root.loaded = true
    })
    Timer { id: saveTimer; interval: 600; onTriggered: root.persist() }
    Timer { id: confirmTimer; interval: 3000; onTriggered: root.confirmDelete = false }
    Component.onDestruction: if (saveTimer.running) root.persist()

    fullRepresentation: GlassCard {
        id: card
        Layout.preferredWidth: 240
        Layout.preferredHeight: 220
        Layout.minimumWidth: 160
        Layout.minimumHeight: 120
        color: root.tints[root.tint].fill
        lit: false

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 6

            RowLayout {
                Layout.fillWidth: true
                spacing: 7
                Repeater {
                    model: root.tints.length
                    Rectangle {
                        required property int index
                        width: 9; height: 9; radius: 4.5
                        color: root.tints[index].dot
                        opacity: root.tint === index ? 1 : 0.35
                        MouseArea {
                            anchors.fill: parent; anchors.margins: -4
                            cursorShape: Qt.PointingHandCursor
                            onClicked: { root.tint = index; root.persist() }
                        }
                    }
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: saveTimer.running ? "saving…" : (root.confirmDelete ? "tap again: kept in Shika" : "")
                    color: root.confirmDelete ? theme.red : theme.faint
                    font.family: theme.font
                    font.pixelSize: 10
                }
                Text {
                    text: "↗"
                    color: openArea.containsMouse ? theme.text : theme.faint
                    font.pixelSize: 13
                    MouseArea {
                        id: openArea
                        anchors.fill: parent; anchors.margins: -4
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (saveTimer.running) { saveTimer.stop(); root.persist() }
                            store.run("open-shika " + store.enc("sticky:" + root.key))
                        }
                    }
                }
                Text {
                    text: "🗑"
                    color: root.confirmDelete ? theme.red : theme.faint
                    font.pixelSize: 12
                    MouseArea {
                        anchors.fill: parent; anchors.margins: -4
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (!root.confirmDelete) { root.confirmDelete = true; confirmTimer.restart(); return }
                            root.confirmDelete = false
                            saveTimer.stop()
                            var last = root.body
                            area.text = ""
                            root.body = ""
                            store.run("note-del " + store.enc(root.key) + " " + store.json({ text: last }))
                        }
                    }
                }
            }

            QQC2.ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                QQC2.TextArea {
                    id: area
                    text: root.body
                    wrapMode: TextEdit.Wrap
                    color: theme.text
                    placeholderText: "Write anything…\nIt stays until you erase it."
                    placeholderTextColor: theme.faint
                    selectionColor: theme.red
                    selectedTextColor: "#ffffff"
                    font.family: theme.font
                    font.pixelSize: 13
                    background: null
                    leftPadding: 0
                    rightPadding: 0
                    onTextChanged: {
                        if (!root.loaded || text === root.body) return
                        root.body = text
                        saveTimer.restart()
                    }
                }
            }
        }
    }
}
