import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.kirigami as Kirigami

Item {
    id: panel
    property var ctl
    property bool dismissTouch: false
    property alias colors: hyperColors
    HyperPalette { id: hyperColors; darkMode: ctl.dark }
    readonly property int pad: 24
    readonly property int gap: 16
    readonly property real inner: width - 2 * pad
    readonly property real half: (inner - gap) / 2
    implicitWidth: 520
    implicitHeight: Math.min(780, ctl.maxPanelHeight)
    function beganInProtectedArea(position) {
        var protectedItems = home.visible ? [brightnessSlider, volumeSlider]
            : (ctl.page === "wifi" || ctl.page === "bluetooth") ? [detailFlick] : []
        for (var i = 0; i < protectedItems.length; i++) {
            var item = protectedItems[i]
            var local = item.mapFromItem(dismissSurface, position.x, position.y)
            if (local.x >= 0 && local.x <= item.width && local.y >= 0 && local.y <= item.height) return true
        }
        return false
    }
    // Observe upward swipes across the sheet while leaving the two vertical
    // adjustment sliders and network/device lists to their own drag handlers.
    Item {
        id: dismissSurface
        anchors.fill: parent; z: 100000
        PointHandler {
            acceptedDevices: PointerDevice.TouchScreen
            onActiveChanged: if (active) panel.dismissTouch = false
            onPointChanged: {
                if (!active || panel.beganInProtectedArea(point.pressPosition)) return
                var dx = point.position.x - point.pressPosition.x
                var dy = point.position.y - point.pressPosition.y
                if (dy < -56 && Math.abs(dy) > Math.abs(dx) * 1.3) {
                    panel.dismissTouch = true
                    ctl.pendingVol = -1
                    ctl.pendingDisp = ({})
                    ctl.closePopup()
                }
            }
        }
    }
    function ic(name) { return ctl.iconBase + name }
    function entry(preset) { return {preset: preset} }
    Rectangle { anchors.fill: parent; radius: 34; color: hyperColors.panel; border.width: 1; border.color: hyperColors.border }

    Item {
        id: header; x: panel.pad; y: 20; width: panel.inner; height: 66
        Text { text: Qt.formatTime(ctl.now, "HH:mm"); color: hyperColors.text; font.pixelSize: 34; font.weight: Font.Light }
        Text { y: 42; text: ctl.uiLocale.toString(ctl.now, "M月d日 dddd"); color: hyperColors.muted; font.pixelSize: 12 }
        Row {
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; spacing: 10
            Text { anchors.verticalCenter: parent.verticalCenter; text: ctl.batteryPercent >= 0 ? ctl.batteryPercent + "%" : ""; color: hyperColors.text; font.pixelSize: 13 }
            Item {
                width: 38; height: 38
                Kirigami.Icon { anchors.centerIn: parent; width: 25; height: 25; source: panel.ic("kc-gear.svg"); isMask: true; color: hyperColors.text }
                MouseArea { anchors.fill: parent; onClicked: ctl.closeAnd("systemsettings") }
            }
        }
    }

    Item {
        id: home; x: panel.pad; y: 104; width: panel.inner; height: panel.height - y - 45
        visible: ctl.page === "main"
        HyperTile {
            colors: panel.colors
            width: panel.half; height: 94
            iconSource: panel.ic("wifi.svg"); title: ctl.wifiOn && ctl.wifiSsid !== "" ? ctl.wifiSsid : "WLAN"
            subtitle: ctl.wifiOn ? (ctl.wifiConn ? "已连接" : "未连接") : "已关闭"
            selected: ctl.wifiOn; details: true
            onClicked: ctl.toggleWifi(); onDetailRequested: ctl.openPage("wifi", "large")
        }
        HyperTile {
            colors: panel.colors
            x: panel.half + panel.gap; width: panel.half; height: 94
            iconSource: panel.ic("kc-bluetooth.svg"); title: "蓝牙"; selected: ctl.btOn; details: true
            subtitle: ctl.btOn ? (ctl.btCount > 0 ? "已连接 " + ctl.btCount + " 台设备" : "已开启") : "已关闭"
            onClicked: ctl.toggleBluetooth(); onDetailRequested: ctl.openPage("bluetooth", "large")
        }
        Rectangle {
            id: media; y: 110; width: panel.half; height: 222; radius: 28; color: hyperColors.card
            Kirigami.Icon { x: 22; y: 20; width: 28; height: 28; source: panel.ic("sheng-music.svg"); isMask: true; color: hyperColors.muted }
            Text { x: 22; y: 66; width: parent.width - 44; text: ctl.mediaActive ? ctl.mediaTitle : "未在播放"; color: hyperColors.text; font.pixelSize: 17; font.weight: Font.Medium; maximumLineCount: 2; wrapMode: Text.WordWrap; elide: Text.ElideRight }
            Text { x: 22; y: 118; width: parent.width - 44; text: ctl.mediaActive ? ctl.mediaArtist : "音乐与媒体"; color: hyperColors.muted; font.pixelSize: 12; elide: Text.ElideRight }
            Row {
                anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 24; spacing: 16
                Repeater {
                    model: ["player-skip-back.svg", ctl.mediaStatus === "Playing" ? "player-pause.svg" : "player-play.svg", "player-skip-forward.svg"]
                    delegate: Item {
                        required property string modelData; required property int index
                        width: 38; height: 38; opacity: ctl.player !== "" ? 1 : 0.35
                        Kirigami.Icon { anchors.centerIn: parent; width: index === 1 ? 32 : 23; height: width; source: panel.ic(modelData); isMask: true; color: hyperColors.text }
                        MouseArea { anchors.fill: parent; enabled: ctl.player !== ""; onClicked: ctl.mpris(index === 0 ? "previous" : index === 1 ? "play-pause" : "next") }
                    }
                }
            }
        }
        HyperSlider {
            id: brightnessSlider
            colors: panel.colors
            cancelTouch: panel.dismissTouch || !ctl.popupOpen
            x: panel.half + panel.gap; y: 110; width: (panel.half - panel.gap) / 2; height: 222
            iconSource: panel.ic("sun.svg"); title: "亮度"; available: ctl.displays.count > 0
            value: ctl.displays.count ? ctl.displays.get(0).dvalue : 0
            onMoved: value => {
                ctl.touch(); var display = ctl.displays.get(0)
                ctl.displays.setProperty(0, "dvalue", value)
                var pending = ctl.pendingDisp; pending[display.dname] = Math.round(value * display.dmax); ctl.pendingDisp = pending
            }
        }
        HyperSlider {
            id: volumeSlider
            colors: panel.colors
            cancelTouch: panel.dismissTouch || !ctl.popupOpen
            x: panel.half + 2 * panel.gap + (panel.half - panel.gap) / 2; y: 110; width: (panel.half - panel.gap) / 2; height: 222
            iconSource: panel.ic("volume.svg"); title: "音量"; value: ctl.muted ? 0 : Math.min(1, ctl.volume)
            onMoved: value => { ctl.touch(); ctl.volume = value; ctl.pendingVol = value; if (ctl.muted) ctl.sh("wpctl set-mute @DEFAULT_AUDIO_SINK@ 0", 250) }
        }
        Grid {
            y: 354; width: parent.width; columns: 4; columnSpacing: 14; rowSpacing: 8
            HyperToggle { colors: panel.colors; width: (panel.inner - 42) / 4; title: "热点"; selected: ctl.hotspotOn; available: !ctl.hotspotBusy; iconSource: panel.ic("sheng-hotspot.svg"); onClicked: ctl.entryClick(panel.entry("sheng-hotspot")) }
            HyperToggle { colors: panel.colors; width: (panel.inner - 42) / 4; title: "飞行模式"; selected: ctl.airplane; iconSource: panel.ic("plane.svg"); onClicked: ctl.toggleAirplane() }
            HyperToggle { colors: panel.colors; width: (panel.inner - 42) / 4; title: "勿扰模式"; selected: ctl.dnd; iconSource: panel.ic("bell-off.svg"); onClicked: ctl.entryClick(panel.entry("dnd")) }
            HyperToggle { colors: panel.colors; width: (panel.inner - 42) / 4; title: "深色模式"; selected: ctl.dark; iconSource: panel.ic("moon.svg"); onClicked: ctl.entryClick(panel.entry("dark")) }
            HyperToggle { colors: panel.colors; width: (panel.inner - 42) / 4; title: "护眼模式"; selected: ctl.night; iconSource: panel.ic("bulb.svg"); onClicked: ctl.entryClick(panel.entry("night")) }
            HyperToggle {
                colors: panel.colors; width: (panel.inner - 42) / 4; title: ctl.privacyError ? "隐私异常" : "隐私"
                selected: ctl.privacyOn && ctl.privacyGuard && !ctl.privacyError
                available: !ctl.privacyBusy && !ctl.privacyServiceBusy
                iconSource: panel.ic("sheng-privacy.svg")
                onClicked: ctl.togglePrivacy()
                QQC2.ToolTip.visible: privacyHover.hovered
                QQC2.ToolTip.text: ctl.privacyHint
                HoverHandler { id: privacyHover }
            }
            HyperToggle { colors: panel.colors; width: (panel.inner - 42) / 4; title: "截屏"; iconSource: panel.ic("sheng-capture.svg"); onClicked: ctl.entryClick(panel.entry("capture")) }
            HyperToggle { colors: panel.colors; width: (panel.inner - 42) / 4; title: "锁屏"; iconSource: panel.ic("lock.svg"); onClicked: ctl.closeAnd("qdbus6 org.freedesktop.ScreenSaver /ScreenSaver org.freedesktop.ScreenSaver.Lock") }
        }
    }

    Item {
        x: panel.pad; y: 102; width: panel.inner; height: panel.height - y - 48; visible: ctl.page !== "main"
        RowLayout {
            id: detailHeader; width: parent.width; height: 42
            QQC2.Button { text: "‹ 返回"; onClicked: ctl.closePage() }
            Text { Layout.fillWidth: true; text: ctl.page === "wifi" ? "WLAN" : ctl.page === "bluetooth" ? "蓝牙" : "声音"; color: hyperColors.text; font.pixelSize: 20 }
            QQC2.Button { text: "刷新"; onClicked: ctl.pageRefresh() }
        }
        Flickable {
            id: detailFlick; anchors.top: detailHeader.bottom; anchors.topMargin: 12; anchors.bottom: parent.bottom; width: parent.width; clip: true
            contentHeight: detailLoader.item ? detailLoader.item.implicitHeight : 0
            Loader { id: detailLoader; width: parent.width; sourceComponent: ctl.page === "wifi" ? wifiPage : ctl.page === "bluetooth" ? bluetoothPage : null }
        }
        Connections { target: ctl; function onPageChanged() { detailFlick.contentY = 0 } }
    }
    Component { id: wifiPage; WifiPage { ctl: panel.ctl } }
    Component { id: bluetoothPage; BluetoothPage { ctl: panel.ctl } }
    Item {
        anchors.bottom: parent.bottom; anchors.horizontalCenter: parent.horizontalCenter; width: 180; height: 42
        Rectangle { anchors.centerIn: parent; width: 74; height: 5; radius: 3; color: hyperColors.muted }
        MouseArea { anchors.fill: parent; onClicked: ctl.closePopup() }
    }
}
