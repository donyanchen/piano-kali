import QtQuick
import QtQuick.Layouts

Item {
    id: integration
    property Item anchor
    readonly property Item host: anchor && anchor.Window.window ? anchor.Window.window.contentItem : null
    property Item clockItem: null
    property Item originalClockParent: null
    property real clockWidth: 80
    property int attempts: 0
    property bool bluetoothBlocked: false
    property bool wifiBlocked: false
    property bool brightnessBlocked: false
    property var ownedBlockers: []
    property var filteredHandlers: []
    Item {
        id: clockLayer
        parent: integration.host
        x: parent ? (parent.width - width) / 2 : 0
        y: 0
        width: integration.clockWidth
        height: parent ? parent.height : 40
        z: 5000
    }
    Component {
        id: touchBlocker
        MultiPointTouchArea {
            objectName: "sheng-mouse-only-tray"
            anchors.fill: parent
            z: 99999
            mouseEnabled: false
            minimumTouchPoints: 1
            maximumTouchPoints: 10
        }
    }
    function collect(item, output, depth) {
        if (!item || depth > 28) return
        if (item.applet && item.applet.plasmoid) output.push(item)
        var children = item.children || []
        for (var i = 0; i < children.length; i++) collect(children[i], output, depth + 1)
    }
    function whiteText(item, depth) {
        if (!item || depth > 18) return
        if ("text" in item && "color" in item) item.color = "#ffffff"
        var children = item.children || []
        for (var i = 0; i < children.length; i++) whiteText(children[i], depth + 1)
    }
    function batteryBadge(item, depth) {
        if (!item || depth > 18) return
        // Keep the percentage readable beside a white symbolic battery.
        if (String(item).indexOf("BadgeOverlay") >= 0 && "customColor" in item) item.customColor = "#b3202a3c"
        var children = item.children || []
        for (var i = 0; i < children.length; i++) batteryBadge(children[i], depth + 1)
    }
    function filterTouchHandlers(item, depth, visited) {
        if (!item || depth > 22 || visited.indexOf(item) >= 0) return
        visited.push(item)
        if ("acceptedDevices" in item) {
            var old = Number(item.acceptedDevices)
            if ((old & PointerDevice.TouchScreen) !== 0) {
                filteredHandlers.push({object: item, devices: old})
                item.acceptedDevices = old & ~PointerDevice.TouchScreen
            }
        }
        var lists = [item.children || [], item.resources || [], item.data || []]
        for (var l = 0; l < lists.length; l++)
            for (var i = 0; i < lists[l].length; i++) filterTouchHandlers(lists[l][i], depth + 1, visited)
    }
    function sync() {
        attempts++
        if (!host) return
        var nodes = []
        collect(host, nodes, 0)
        for (var i = 0; i < nodes.length; i++) {
            var item = nodes[i]
            var name = item.applet.plasmoid.pluginName
            if (name === "org.kde.plasma.battery") batteryBadge(item, 0)
            if (name === "org.kde.plasma.digitalclock" && String(item).indexOf("AppletContainer") >= 0) {
                if (clockItem !== item) {
                    clockWidth = item.width
                    originalClockParent = item.parent
                    clockItem = item
                    item.parent = clockLayer
                    item.anchors.centerIn = clockLayer
                    item.width = clockWidth
                    item.height = 32
                }
                whiteText(item, 0)
            }
            if (name === "org.kde.plasma.bluetooth" || name === "org.kde.plasma.networkmanagement" || name === "org.kde.plasma.brightness") {
                if (name === "org.kde.plasma.brightness") {
                    var visited = []
                    filterTouchHandlers(item, 0, visited)
                    filterTouchHandlers(item.applet, 0, visited)
                    if (item.applet.compactRepresentationItem) filterTouchHandlers(item.applet.compactRepresentationItem, 0, visited)
                }
                if (!item.visible || item.width < 2 || item.height < 2) continue
                var found = false
                for (var j = 0; j < item.children.length; j++) if (item.children[j].objectName === "sheng-mouse-only-tray") found = true
                if (!found) ownedBlockers.push(touchBlocker.createObject(item))
                if (name === "org.kde.plasma.bluetooth") bluetoothBlocked = true
                else if (name === "org.kde.plasma.networkmanagement") wifiBlocked = true
                else brightnessBlocked = true
            }
        }
    }
    onHostChanged: { attempts = 0; scan.restart() }
    Component.onDestruction: {
        for (var i = 0; i < ownedBlockers.length; i++) if (ownedBlockers[i]) ownedBlockers[i].destroy()
        for (var j = 0; j < filteredHandlers.length; j++) {
            var entry = filteredHandlers[j]
            if (entry.object) entry.object.acceptedDevices = entry.devices
        }
        if (clockItem && originalClockParent) {
            clockItem.anchors.centerIn = null
            clockItem.parent = originalClockParent
        }
    }
    Timer {
        id: scan
        interval: 500
        running: integration.host !== null
        repeat: true
        onTriggered: {
            integration.sync()
            if ((integration.clockItem && integration.bluetoothBlocked && integration.wifiBlocked && integration.brightnessBlocked) || integration.attempts >= 12) {
                console.info("SHENG_PANEL_TOUCH_FILTER", integration.bluetoothBlocked, integration.wifiBlocked, integration.brightnessBlocked, integration.filteredHandlers.length)
                stop()
            }
        }
    }
}
