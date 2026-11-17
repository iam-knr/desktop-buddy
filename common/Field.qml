import QtQuick
import QtQuick.Controls as QQC2

// Borderless text field with a hairline underline that turns red on focus.
QQC2.TextField {
    id: f
    property QtObject theme: Theme {}
    color: theme.text
    placeholderTextColor: theme.faint
    selectionColor: theme.red
    selectedTextColor: "#ffffff"
    font.family: theme.font
    font.pixelSize: 13
    leftPadding: 2
    rightPadding: 2
    background: Item {
        implicitHeight: 32
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: f.activeFocus ? f.theme.red : f.theme.line
        }
    }
}
