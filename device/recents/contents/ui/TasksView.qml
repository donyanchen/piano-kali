import QtQuick
import QtQuick.Effects
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami
import org.kde.kwin as KWin

FocusScope {
    id: view
    required property var controller
    readonly property var targetScreen: KWin.SceneView.screen
    readonly property bool darkMode: Kirigami.Theme.backgroundColor.hslLightness < 0.5
    readonly property color ink: darkMode ? "#f8f9fc" : "#20232b"
    property real reveal: 0
    NumberAnimation { id: opening; target: view; property: "reveal"; to: 1; duration: 220; easing.type: Easing.OutCubic }
    NumberAnimation { id: closing; target: view; property: "reveal"; to: 0; duration: 220; easing.type: Easing.InCubic }
    Connections {
        target: controller
        function onExpandedChanged() {
            if (!controller.expanded) { opening.stop(); closing.start() }
        }
    }
    focus: true

    KWin.DesktopBackground {
        anchors.fill: parent
        outputName: view.targetScreen.name
        desktop: view.KWin.SceneView.currentDesktop
        activity: KWin.Workspace.currentActivity
        layer.enabled: true
        layer.effect: MultiEffect { blurEnabled: true; blurMax: 64; blur: 0.75 * view.reveal }
    }
    Rectangle {
        anchors.fill: parent
        color: view.darkMode ? "#202431" : "#eef1f6"
        opacity: 0.60 * view.reveal
        TapHandler { onTapped: controller.dismiss(null) }
    }
    Item {
        anchors.fill: parent
        opacity: view.reveal
        scale: 0.97 + 0.03 * view.reveal
        transform: Translate { y: (1 - view.reveal) * 30 }

        Row {
            x: 56; y: 44; spacing: 14
            Text { text: "最近任务"; color: view.ink; font.pixelSize: 30; font.weight: Font.DemiBold }
            Text { anchors.baseline: parent.children[0].baseline; text: controller.entries.length + " 个窗口"; color: view.ink; opacity: 0.5; font.pixelSize: 14 }
        }
        QQC2.Button {
            anchors.right: parent.right; anchors.rightMargin: 50; y: 44
            text: "完成"
            onClicked: controller.dismiss(null)
        }
        GridView {
            id: cards
            x: Math.max(48, (parent.width - width) / 2); y: 115
            width: Math.min(parent.width - 96, 1280)
            height: parent.height - y - 122
            clip: true
            readonly property int columns: width >= 1000 ? 4 : width >= 700 ? 3 : 2
            cellWidth: width / columns
            cellHeight: (cellWidth - 28) / 1.5 + 69
            model: controller.entries
            currentIndex: controller.selectedIndex
            boundsBehavior: Flickable.StopAtBounds
            QQC2.ScrollBar.vertical: QQC2.ScrollBar { }
            delegate: Item {
                required property var modelData
                required property int index
                width: cards.cellWidth; height: cards.cellHeight
                TaskCard {
                    width: parent.width - 28; height: parent.height - 24; anchors.horizontalCenter: parent.horizontalCenter
                    client: modelData; controller: view.controller; darkMode: view.darkMode
                    selected: index === controller.selectedIndex
                    onActivated: controller.dismiss(client)
                    onCloseRequested: controller.closeWindow(client)
                }
            }
            onCurrentIndexChanged: positionViewAtIndex(currentIndex, GridView.Contain)
        }
        Text {
            visible: !controller.entries.length
            anchors.centerIn: parent
            text: "暂无最近任务"; color: view.ink; opacity: 0.55; font.pixelSize: 22
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom; anchors.bottomMargin: 20
            text: "轻点卡片打开 · 上滑卡片关闭"
            color: view.ink; opacity: 0.5; font.pixelSize: 13
        }
        Rectangle {
            visible: controller.entries.length > 0
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom; anchors.bottomMargin: 50
            width: 52; height: 52; radius: 26
            color: view.darkMode ? "#24ffffff" : "#b3ffffff"
            Text { anchors.centerIn: parent; text: "×"; color: view.ink; font.pixelSize: 30; font.weight: Font.Light }
            QQC2.ToolTip.visible: clearHover.hovered
            QQC2.ToolTip.text: "全部关闭"
            HoverHandler { id: clearHover }
            TapHandler { onTapped: controller.closeAll() }
        }
    }
    Keys.onEscapePressed: controller.dismiss(null)
    Keys.onLeftPressed: controller.moveSelection(-1)
    Keys.onRightPressed: controller.moveSelection(1)
    Keys.onUpPressed: controller.moveSelection(-cards.columns)
    Keys.onDownPressed: controller.moveSelection(cards.columns)
    Keys.onReturnPressed: { if (controller.entries.length) controller.dismiss(controller.entries[controller.selectedIndex]) }
    Keys.onEnterPressed: { if (controller.entries.length) controller.dismiss(controller.entries[controller.selectedIndex]) }
    Keys.onTabPressed: controller.moveSelection(1)
    Component.onCompleted: { Qt.callLater(opening.start); forceActiveFocus() }
}
