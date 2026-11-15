// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

Item {
    id: glyph
    objectName: "sheng-battery-glyph"
    required property Item battery
    readonly property int percent: Math.max(0, Math.min(100, Number(battery.batteryPercent)))
    anchors.fill: parent
    z: 10000
    Accessible.role: Accessible.Indicator
    Accessible.name: percent + "%" + (battery.batteryPluggedIn ? "，已连接电源" : "")
    Item {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.horizontalCenterOffset: 4
        anchors.verticalCenter: parent.verticalCenter
        width: Math.min(parent.width - 4, 35)
        height: 18
        Rectangle {
            id: body
            width: parent.width - 3
            height: parent.height
            radius: 5
            color: "#203c4858"
            border.color: "white"
            border.width: 1.5
            Rectangle {
                x: 3; y: 3
                width: Math.max(0, (parent.width - 6) * glyph.percent / 100)
                height: parent.height - 6
                radius: 2
                color: "#50ffffff"
            }
            Text {
                anchors.centerIn: parent
                text: glyph.percent
                color: "white"
                font.pixelSize: 10
                font.weight: Font.DemiBold
                renderType: Text.QtRendering
            }
        }
        Rectangle {
            anchors.left: body.right
            anchors.leftMargin: 1
            anchors.verticalCenter: body.verticalCenter
            width: 2; height: 7; radius: 1
            color: "white"
        }
        Rectangle {
            visible: glyph.battery.batteryPluggedIn
            x: -4; y: 7
            width: 3; height: 3; radius: 1.5
            color: "white"
        }
    }
}
