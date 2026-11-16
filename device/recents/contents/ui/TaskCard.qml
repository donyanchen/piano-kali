import QtQuick
import QtQuick.Effects
import org.kde.kwin as KWin
import org.kde.kirigami as Kirigami

Item {
    id: card
    required property var client
    required property var controller
    property bool selected: false
    property bool darkMode: false
    property bool compact: false
    property real lift: 0
    readonly property color ink: darkMode ? "#f8f9fc" : "#20232b"
    signal activated()
    signal closeRequested()

    transform: Translate { y: card.lift }
    opacity: Math.max(0.25, 1 - Math.abs(lift) / height)
    Behavior on lift { enabled: !drag.active; NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

    Row {
        x: 10; y: 0; width: parent.width - 48; height: 40; spacing: 10
        Kirigami.Icon { width: 28; height: 28; anchors.verticalCenter: parent.verticalCenter; source: card.client ? card.client.icon : "application-x-executable" }
        Text {
            width: parent.width - 38; anchors.verticalCenter: parent.verticalCenter
            text: card.client ? card.client.caption : ""
            color: card.ink; font.pixelSize: card.compact ? 13 : 15; font.weight: Font.Medium
            elide: Text.ElideRight
        }
    }
    Item {
        x: parent.width - 38; y: 2; width: 36; height: 36
        visible: card.client && card.client.closeable && !card.compact
        Text { anchors.centerIn: parent; text: "×"; font.pixelSize: 23; color: card.ink; opacity: 0.6 }
        TapHandler { onTapped: card.closeRequested() }
    }
    Rectangle {
        id: preview
        y: 45; width: parent.width; height: parent.height - y; radius: 24
        color: card.darkMode ? "#252833" : "#f7f8fc"
        border.width: card.selected ? 3 : 1
        border.color: card.selected ? Kirigami.Theme.highlightColor : (card.darkMode ? "#26ffffff" : "#18000000")
        layer.enabled: true
        layer.effect: MultiEffect {
            maskEnabled: true
            maskSource: mask
            maskThresholdMin: 0.5
            maskSpreadAtMin: 1
        }
        KWin.WindowThumbnail {
            anchors.fill: parent; anchors.margins: 3
            client: card.client
        }
    }
    Rectangle {
        id: mask
        y: preview.y; width: preview.width; height: preview.height
        radius: preview.radius; color: "white"; visible: false; layer.enabled: true
    }
    TapHandler {
        gesturePolicy: TapHandler.DragThreshold
        onTapped: point => {
            if (card.compact || point.position.y > 42 || point.position.x < card.width - 42)
                card.activated()
        }
    }
    DragHandler {
        id: drag
        enabled: !card.compact
        target: null
        xAxis.enabled: false
        yAxis.enabled: true
        onTranslationChanged: card.lift = Math.min(0, translation.y)
        onActiveChanged: {
            if (!active) {
                if (card.lift < -90) card.closeRequested()
                card.lift = 0
            }
        }
    }
}
