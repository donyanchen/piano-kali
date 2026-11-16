/*
    SPDX-FileCopyrightText: 2026 Petexy
    SPDX-FileCopyrightText: 2026 Sheng Kali contributors
    SPDX-License-Identifier: GPL-3.0-or-later
*/
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid

Item {
    id: root
    implicitWidth: dock.implicitWidth
    implicitHeight: 84
    Layout.minimumWidth: implicitWidth
    Layout.preferredWidth: implicitWidth
    Layout.maximumWidth: implicitWidth
    Layout.minimumHeight: 64
    Layout.preferredHeight: 84
    Layout.fillWidth: false
    property Component dashWindowComponent: null
    property var dashWindow: null
    function toggleDrawer() { if (dashWindow) { dashWindow.toggleWithDock(); justOpenedTimer.start() } }
    Component.onCompleted: {
        dashWindowComponent = Qt.createComponent(Qt.resolvedUrl("DashboardRepresentation.qml"))
        function createWindow() {
            if (dashWindowComponent.status === Component.Ready)
                dashWindow = dashWindowComponent.createObject(root, {visualParent: dock})
            else if (dashWindowComponent.status === Component.Error)
                console.error("Linexin Dock:", dashWindowComponent.errorString())
        }
        createWindow()
        if (dashWindowComponent.status === Component.Loading)
            dashWindowComponent.statusChanged.connect(createWindow)
    }
    Connections { target: Plasmoid; function onActivated() { root.toggleDrawer() } }
    ShengDock {
        id: dock
        anchors.fill: parent
        onDrawerRequested: root.toggleDrawer()
        onAppActivated: if (root.dashWindow && root.dashWindow.visible) root.dashWindow.closeWithAnimation()
    }
}
