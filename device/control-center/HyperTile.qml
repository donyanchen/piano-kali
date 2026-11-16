import QtQuick
import org.kde.kirigami as Kirigami

Rectangle {
    id: tile
    required property var colors
    property string iconSource
    property string title
    property string subtitle
    property bool selected: false
    property bool busy: false
    property bool details: false
    signal clicked()
    signal detailRequested()
    radius: 26
    color: selected ? colors.active : colors.card
    opacity: tap.pressed ? 0.82 : 1
    Behavior on color { ColorAnimation { duration: 160 } }
    Kirigami.Icon {
        x: 20; anchors.verticalCenter: parent.verticalCenter
        width: 32; height: 32; source: tile.iconSource; isMask: true; color: tile.selected ? tile.colors.activeText : tile.colors.text
    }
    Column {
        x: 66; anchors.verticalCenter: parent.verticalCenter
        width: parent.width - x - (tile.details ? 38 : 16); spacing: 5
        Text { width: parent.width; text: tile.title; color: tile.selected ? tile.colors.activeText : tile.colors.text; font.pixelSize: 17; font.weight: Font.DemiBold; elide: Text.ElideRight }
        Text { width: parent.width; text: tile.busy ? "正在切换…" : tile.subtitle; color: tile.selected ? tile.colors.activeMuted : tile.colors.muted; font.pixelSize: 12; elide: Text.ElideRight }
    }
    MouseArea { id: tap; anchors.fill: parent; enabled: !tile.busy; onClicked: tile.clicked(); onPressAndHold: if (tile.details) tile.detailRequested() }
    Text { visible: tile.details; anchors.right: parent.right; anchors.rightMargin: 16; anchors.verticalCenter: parent.verticalCenter; text: "›"; color: tile.selected ? tile.colors.activeText : tile.colors.muted; font.pixelSize: 28 }
    MouseArea { visible: tile.details; anchors.right: parent.right; width: 42; height: parent.height; onClicked: tile.detailRequested() }
}
