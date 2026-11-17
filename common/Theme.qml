import QtQuick

// Summit look: subtle dark glass, white type, red only for what's urgent.
QtObject {
    readonly property color glass: Qt.rgba(0.035, 0.035, 0.045, 0.62)
    readonly property color glassHover: Qt.rgba(0.06, 0.06, 0.075, 0.70)
    readonly property color edge: Qt.rgba(1, 1, 1, 0.10)
    readonly property color sheen: Qt.rgba(1, 1, 1, 0.055)
    readonly property color text: "#F2F2F3"
    readonly property color muted: Qt.rgba(1, 1, 1, 0.55)
    readonly property color faint: Qt.rgba(1, 1, 1, 0.28)
    readonly property color line: Qt.rgba(1, 1, 1, 0.08)
    readonly property color red: "#E11D2E"
    readonly property color redSoft: Qt.rgba(0.88, 0.11, 0.18, 0.18)
    readonly property int radius: 18
    readonly property string font: "Noto Sans"
}
