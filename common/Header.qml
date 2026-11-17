import QtQuick
import QtQuick.Layouts

// Small spaced-out caps label, echoing the "— NIMSDAI" line on the wallpaper.
RowLayout {
    property string title: ""
    property string detail: ""
    property QtObject theme: Theme {}
    spacing: 8
    Rectangle { width: 14; height: 1; color: theme.red; Layout.alignment: Qt.AlignVCenter }
    Text {
        text: title.toUpperCase()
        color: theme.text
        font.family: theme.font
        font.pixelSize: 11
        font.letterSpacing: 3
        font.weight: Font.DemiBold
    }
    Item { Layout.fillWidth: true }
    Text {
        text: detail
        color: theme.muted
        font.family: theme.font
        font.pixelSize: 11
        visible: detail.length > 0
    }
}
