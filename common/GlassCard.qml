import QtQuick

// A frosted card: dark translucent body, hairline white edge, faint top sheen.
Rectangle {
    id: card
    property QtObject theme: Theme {}
    property bool lit: false
    radius: theme.radius
    color: lit ? theme.glassHover : theme.glass
    border.width: 1
    border.color: theme.edge
    Behavior on color { ColorAnimation { duration: 180 } }

    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        radius: card.radius - 1
        gradient: Gradient {
            GradientStop { position: 0.0; color: card.theme.sheen }
            GradientStop { position: 0.28; color: "transparent" }
        }
    }
}
