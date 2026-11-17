import QtQuick

// Small glass pill button. "active" tints it red.
Rectangle {
    id: chip
    property string label: ""
    property bool active: false
    property QtObject theme: Theme {}
    signal clicked()
    implicitWidth: txt.implicitWidth + 20
    implicitHeight: 26
    radius: 13
    color: active ? theme.redSoft : (ma.containsMouse ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.04))
    border.width: 1
    border.color: active ? theme.red : (ma.containsMouse ? Qt.rgba(1, 1, 1, 0.22) : theme.line)
    Behavior on color { ColorAnimation { duration: 120 } }
    Text {
        id: txt
        anchors.centerIn: parent
        text: chip.label
        color: chip.active ? "#FFD6DA" : chip.theme.text
        font.family: chip.theme.font
        font.pixelSize: 11
    }
    MouseArea {
        id: ma
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: chip.clicked()
    }
}
