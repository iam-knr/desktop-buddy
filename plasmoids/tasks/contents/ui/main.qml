import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore

// Tasks and reminders in one list. Type, pick a time (optional for tasks),
// then "+ Task" or "Remind me". Anything with a time makes Shika bark when due.
// Data: ~/.config/shika/reminders.json (shared with Shika and voice commands).
PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation

    property var items: []
    property bool shika: true
    property double quietUntil: 0
    property double now: Date.now()
    property int when: 0                 // index into whenChoices
    property int repeatIdx: 0
    property string warning: ""
    property var inputRef: null
    property var timeRef: null

    readonly property var whenChoices: ["No time", "+15 min", "+1 hr", "8 PM", "Tmrw 9 AM"]
    readonly property var repeats: [
        { label: "Once", min: 0 }, { label: "Hourly", min: 60 },
        { label: "Daily", min: 1440 }, { label: "Weekly", min: 10080 }]
    readonly property int openCount: items.filter(function (t) { return !t.done }).length
    readonly property int doneCount: items.filter(function (t) { return t.done }).length
    readonly property var view: {
        var a = items.map(function (t, i) { return { t: t, i: i } })
        function rank(t) {
            if (t.done) return 3
            if (t.due) return 0
            return t.urgent ? 1 : 2
        }
        a.sort(function (x, y) {
            return rank(x.t) - rank(y.t) || ((x.t.due || 0) - (y.t.due || 0)) || x.i - y.i
        })
        return a.map(function (x) { return x.t })
    }

    Theme { id: theme }
    Store { id: store }

    function load() {
        if (Date.now() < quietUntil) return
        store.get("items", function (d) {
            if (Date.now() < root.quietUntil) return
            root.items = d.items || []
            root.shika = d.shika
        })
    }
    function afterWrite() { root.quietUntil = 0; root.load() }
    function hold() { quietUntil = Date.now() + 3000 }

    function patch(id, fields) {
        hold()
        items = items.map(function (t) { return t.id === id ? Object.assign({}, t, fields) : t })
        store.run("item-update " + store.enc(id) + " " + store.json(fields), afterWrite)
    }
    function remove(id) {
        hold()
        items = items.filter(function (t) { return t.id !== id })
        store.run("item-del " + store.enc(id), afterWrite)
    }
    function clearDone() {
        hold()
        items = items.filter(function (t) { return !(t.kind === "task" && t.done) })
        store.run("clear-done", afterWrite)
    }

    function at(h, m, dayOffset) {
        var d = new Date(); d.setDate(d.getDate() + dayOffset); d.setHours(h, m, 0, 0)
        return Math.floor(d.getTime() / 1000)
    }
    // Accepts 6:45 pm, 6.45pm, 18:45, 6 pm, 6, and a day in front: "tmrw 5:30 pm", "tomorrow 9".
    function parseTime(s) {
        var t = s.trim().toLowerCase().replace(/\b([ap])\.?\s?m\.?/g, "$1m")
        var dayOffset = -1
        var dm = t.match(/^(tmrw|tmr|tomorrow|tom|today)\s+/)
        if (dm) {
            dayOffset = dm[1] === "today" ? 0 : 1
            t = t.slice(dm[0].length)
        }
        var m = t.match(/^(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?$/)
        if (!m) return -1
        var h = parseInt(m[1]), mi = m[2] ? parseInt(m[2]) : 0
        if (h > 23 || mi > 59 || (m[3] && h > 12)) return -1
        var options
        if (m[3]) options = [(h % 12) + (m[3] === "pm" ? 12 : 0)]
        else if (dayOffset === 1 && h <= 12) options = [(h >= 7 && h <= 11) ? h : (h === 12 ? 12 : h + 12)]
        else options = h < 12 ? [h, h + 12] : [h]
        var days = dayOffset >= 0 ? [dayOffset] : [0, 1]
        var best = 0
        for (var i = 0; i < options.length; i++)
            for (var j = 0; j < days.length; j++) {
                var ts = at(options[i], mi, days[j])
                if (ts * 1000 > Date.now() && (!best || ts < best)) best = ts
            }
        return best || -1
    }
    function chosenDue() {                // 0 = no time, -1 = invalid typed time
        if (timeRef && timeRef.text.trim()) return parseTime(timeRef.text)
        var nowS = Math.floor(Date.now() / 1000)
        switch (when) {
        case 1: return nowS + 15 * 60
        case 2: return nowS + 60 * 60
        case 3: var t = at(20, 0, 0); return t > nowS ? t : at(20, 0, 1)
        case 4: return at(9, 0, 1)
        }
        return 0
    }
    function add(kind) {
        var text = inputRef ? inputRef.text.trim() : ""
        if (!text) { warn("Type something first"); return }
        var due = chosenDue()
        if (due < 0) { warn("Try 6:45 pm, 18:45 or tmrw 5:30 pm"); return }
        if (kind === "reminder" && !due) { warn("Pick a time for the reminder"); return }
        var item = { kind: kind, text: text, due: due || null,
                     repeat: due ? repeats[repeatIdx].min : 0, urgent: false }
        hold()
        items = items.concat([Object.assign({ id: "new" + Date.now(), done: false }, item)])
        store.run("item-add " + store.json(item), afterWrite)
        inputRef.text = ""
        if (timeRef) timeRef.text = ""
        when = 0
        repeatIdx = 0
        warning = ""
    }
    function warn(t) { warning = t; warnTimer.restart() }
    function label(due) {
        var diff = due - now / 1000
        if (diff < 0) return "overdue"
        if (diff < 3600) return "in " + Math.max(1, Math.round(diff / 60)) + " min"
        var d = new Date(due * 1000), t = Qt.formatTime(d, "h:mm AP")
        if (d.toDateString() === new Date(now).toDateString()) return t
        if (d.toDateString() === new Date(now + 86400000).toDateString()) return "Tmrw " + t
        return Qt.formatDate(d, "ddd d MMM") + " · " + t
    }

    Component.onCompleted: load()
    Timer { interval: 4000; running: true; repeat: true; onTriggered: root.load() }
    Timer { interval: 20000; running: true; repeat: true; onTriggered: root.now = Date.now() }
    Timer { id: warnTimer; interval: 4000; onTriggered: root.warning = "" }

    fullRepresentation: GlassCard {
        Layout.preferredWidth: 340
        Layout.preferredHeight: 440
        Layout.minimumWidth: 260
        Layout.minimumHeight: 280

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 10

            Header {
                Layout.fillWidth: true
                title: "Tasks & reminders"
                detail: root.openCount === 0 ? "all clear" : root.openCount + " open"
            }

            Text {
                Layout.fillWidth: true
                visible: !root.shika
                text: "Shika is asleep, so nothing will bark. Click to wake him."
                wrapMode: Text.WordWrap
                color: theme.red
                font.family: theme.font
                font.pixelSize: 11
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: store.run("launch-shika")
                }
            }

            ListView {
                id: list
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 2
                model: root.view
                boundsBehavior: Flickable.StopAtBounds

                delegate: Item {
                    id: row
                    required property var modelData
                    readonly property bool isTask: row.modelData.kind === "task"
                    readonly property bool late: !!row.modelData.due && !row.modelData.done
                                                 && row.modelData.due * 1000 < root.now
                    readonly property bool hot: hov.containsMouse
                    width: ListView.view.width
                    height: 36

                    MouseArea { id: hov; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton }
                    Rectangle {
                        anchors.fill: parent; radius: 10
                        color: row.hot ? Qt.rgba(1, 1, 1, 0.04) : "transparent"
                    }
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 6
                        anchors.rightMargin: 6
                        spacing: 10

                        Item {
                            Layout.preferredWidth: 16
                            Layout.preferredHeight: 16
                            Rectangle {      // task: checkbox circle
                                anchors.fill: parent
                                visible: row.isTask
                                radius: 8
                                color: row.modelData.done ? theme.faint : "transparent"
                                border.width: 1.5
                                border.color: row.modelData.done ? "transparent"
                                            : (row.modelData.urgent || row.late ? theme.red : theme.muted)
                                Text {
                                    anchors.centerIn: parent
                                    visible: row.modelData.done
                                    text: "✓"; color: "#0b0b0b"
                                    font.pixelSize: 10; font.bold: true
                                }
                                MouseArea {
                                    anchors.fill: parent; anchors.margins: -6
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.patch(row.modelData.id, { done: !row.modelData.done })
                                }
                            }
                            Text {           // reminder: bell
                                anchors.centerIn: parent
                                visible: !row.isTask
                                text: "⏰"
                                font.pixelSize: 12
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: row.modelData.text
                            color: row.modelData.done ? theme.faint : theme.text
                            font.strikeout: row.modelData.done
                            font.family: theme.font
                            font.pixelSize: 13
                            elide: Text.ElideRight
                        }
                        Text {
                            visible: !!row.modelData.due && !row.modelData.done
                            text: (row.modelData.repeat ? "↻ " : "") + (row.modelData.due ? root.label(row.modelData.due) : "")
                            color: row.late ? theme.red : theme.muted
                            font.family: theme.font
                            font.pixelSize: 11
                        }
                        Text {
                            text: "⚑"
                            visible: row.isTask && !row.modelData.done && (row.hot || row.modelData.urgent)
                            color: row.modelData.urgent ? theme.red : theme.faint
                            font.pixelSize: 13
                            MouseArea {
                                anchors.fill: parent; anchors.margins: -4
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.patch(row.modelData.id, { urgent: !row.modelData.urgent })
                            }
                        }
                        Text {
                            text: "✕"
                            visible: row.hot
                            color: theme.muted
                            font.pixelSize: 11
                            MouseArea {
                                anchors.fill: parent; anchors.margins: -4
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.remove(row.modelData.id)
                            }
                        }
                    }
                }

                Text {
                    parent: list
                    anchors.centerIn: parent
                    visible: root.items.length === 0
                    text: "Nothing yet.\nType below, or hold Right Alt and say\n“add task …” / “remind me at 5 to …”"
                    horizontalAlignment: Text.AlignHCenter
                    color: theme.faint
                    font.family: theme.font
                    font.pixelSize: 12
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Field {
                    id: input
                    Layout.fillWidth: true
                    placeholderText: "Type a task or reminder…"
                    onAccepted: root.add(root.chosenDue() > 0 ? "reminder" : "task")
                    Component.onCompleted: root.inputRef = input
                }
                Field {
                    id: timeIn
                    Layout.preferredWidth: 96
                    placeholderText: "tmrw 5:30 pm"
                    onTextChanged: if (text.length) root.when = 0
                    onAccepted: root.add("reminder")
                    Component.onCompleted: root.timeRef = timeIn
                }
            }

            Flow {
                Layout.fillWidth: true
                spacing: 6
                Repeater {
                    model: root.whenChoices
                    Chip {
                        required property var modelData
                        required property int index
                        label: modelData
                        active: root.when === index && index > 0
                        onClicked: { root.when = index; timeIn.text = "" }
                    }
                }
                Chip {
                    visible: root.when > 0 || timeIn.text.length > 0
                    label: "↻ " + root.repeats[root.repeatIdx].label
                    active: root.repeatIdx > 0
                    onClicked: root.repeatIdx = (root.repeatIdx + 1) % root.repeats.length
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Chip { label: "＋ Task"; onClicked: root.add("task") }
                Chip { label: "⏰ Remind me"; active: true; onClicked: root.add("reminder") }
                Item { Layout.fillWidth: true }
                Chip { label: "Clear done"; visible: root.doneCount > 0; onClicked: root.clearDone() }
            }

            Text {
                Layout.fillWidth: true
                visible: root.warning.length > 0
                text: root.warning
                color: theme.red
                font.family: theme.font
                font.pixelSize: 11
            }
        }
    }
}
