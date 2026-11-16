import QtQuick
import org.kde.kirigami as Kirigami

Item {
    id: toggle
    required property var colors
    property string iconSource
    property string title
    property bool selected: false
    property bool available: true
    signal clicked()
    signal held()
    implicitHeight: 104
    opacity: available ? 1 : 0.36
    Rectangle {
        width: 72; height: 72; radius: 36
        anchors.horizontalCenter: parent.horizontalCenter
        color: toggle.selected ? toggle.colors.active : toggle.colors.card
        scale: tap.pressed ? 0.94 : 1
        Behavior on color { ColorAnimation { duration: 160 } }
        Behavior on scale { NumberAnimation { duration: 100 } }
        Kirigami.Icon { anchors.centerIn: parent; width: 28; height: 28; source: toggle.iconSource; isMask: true; color: toggle.selected ? toggle.colors.activeText : toggle.colors.text }
        MouseArea { id: tap; anchors.fill: parent; enabled: toggle.available; onClicked: toggle.clicked(); onPressAndHold: toggle.held() }
    }
    Text { y: 81; width: parent.width; horizontalAlignment: Text.AlignHCenter; color: toggle.colors.text; text: toggle.title; font.pixelSize: 12; elide: Text.ElideRight }
}
