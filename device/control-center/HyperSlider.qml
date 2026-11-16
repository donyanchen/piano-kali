import QtQuick
import org.kde.kirigami as Kirigami
Rectangle {
    id: slider
    required property var colors
    property string iconSource
    property string title
    property real value: 0
    property bool available: true
    property bool cancelTouch: false
    property real preview: -1
    readonly property real shownValue: preview >= 0 ? preview : value
    signal moved(real value)
    function at(y) { return Math.max(0, Math.min(1, 1 - y / height)) }
    radius: 30; color: colors.sliderBase
    opacity: available ? 1 : 0.35
    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width; height: parent.height * Math.max(0, Math.min(1, slider.shownValue))
        color: slider.colors.sliderFill
        bottomLeftRadius: 30; bottomRightRadius: 30
        topLeftRadius: slider.shownValue > 0.96 ? 30 : 0
        topRightRadius: slider.shownValue > 0.96 ? 30 : 0
    }
    Rectangle {
        anchors.top: parent.top; anchors.topMargin: 16; anchors.horizontalCenter: parent.horizontalCenter
        width: 58; height: 26; radius: 13; color: slider.colors.readout
        Text { anchors.centerIn: parent; text: Math.round(slider.shownValue * 100) + "%"; font.pixelSize: 14; font.weight: Font.Medium; color: slider.colors.text }
    }
    Kirigami.Icon { anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 26; width: 28; height: 28; source: slider.iconSource; isMask: true; color: slider.shownValue > 0.25 ? slider.colors.sliderInk : slider.colors.muted }
    TapHandler {
        enabled: slider.available
        onTapped: eventPoint => slider.moved(slider.at(eventPoint.position.y))
    }
    DragHandler {
        target: null; enabled: slider.available
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onActiveTranslationChanged: if (active) slider.moved(slider.at(centroid.position.y))
    }
    DragHandler {
        target: null; enabled: slider.available
        acceptedDevices: PointerDevice.TouchScreen
        onActiveChanged: {
            if (active) slider.preview = slider.value
            else {
                var finalValue = slider.preview
                slider.preview = -1
                if (finalValue >= 0 && !slider.cancelTouch) slider.moved(finalValue)
            }
        }
        onActiveTranslationChanged: if (active) {
            slider.preview = slider.at(centroid.position.y)
            slider.moved(slider.preview)
        }
    }
    WheelHandler {
        target: null; enabled: slider.available
        onWheel: event => slider.moved(Math.max(0, Math.min(1, slider.value + (event.angleDelta.y > 0 ? 0.03 : -0.03))))
    }
    Text { anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 7; text: slider.title; color: slider.colors.sliderInk; font.pixelSize: 10 }
}
