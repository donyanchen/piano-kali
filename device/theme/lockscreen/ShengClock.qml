// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: clock
    property real availableWidth: 1000
    property date wallTime: new Date()
    spacing: 8
    Text {
        text: Qt.formatTime(clock.wallTime, "HH:mm")
        color: "white"
        font.family: "Noto Sans CJK SC"
        font.pixelSize: Math.max(64, Math.min(112, clock.availableWidth * 0.09))
        font.weight: Font.Medium
        renderType: Text.QtRendering
        Layout.alignment: Qt.AlignHCenter
    }
    Text {
        text: Qt.locale().toString(clock.wallTime, "M月d日 dddd")
        color: "white"
        font.family: "Noto Sans CJK SC"
        font.pixelSize: Math.max(20, Math.min(28, clock.availableWidth * 0.022))
        renderType: Text.QtRendering
        Layout.alignment: Qt.AlignHCenter
    }
    Timer {
        interval: 1000
        repeat: true
        running: clock.visible
        onTriggered: clock.wallTime = new Date()
    }
    onVisibleChanged: if (visible) wallTime = new Date()
}
