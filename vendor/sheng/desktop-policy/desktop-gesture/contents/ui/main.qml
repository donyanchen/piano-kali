import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support

PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation
    implicitWidth: 1
    implicitHeight: 1
    Layout.minimumWidth: 1
    Layout.minimumHeight: 1
    fullRepresentation: Item { implicitWidth: 1; implicitHeight: 1 }
    property Item desktopLayout: null
    property bool suppressHoldEditing: false
    readonly property int nativeHoldInterval: {
        var hints = Qt.styleHints
        var duration = hints ? Number(hints["mousePressAndHoldInterval"]) : 800
        return Number.isFinite(duration) && duration > 0 ? Math.ceil(duration) : 800
    }
    readonly property int touchDragThreshold: {
        var hints = Qt.styleHints
        var distance = hints ? Number(hints["startDragDistance"]) : 10
        if (!Number.isFinite(distance) || distance <= 0) distance = 10
        // Claim touch motion before Folder View's mouse-style drag selection.
        return Math.max(1, Math.min(3, Math.floor(distance / 2)))
    }

    function findDesktopLayout(item, depth) {
        if (!item || depth > 28) return null
        if ("eventManagerToFilter" in item && "editModeCondition" in item) return item
        var children = item.children || []
        for (var i = 0; i < children.length; ++i) {
            var result = findDesktopLayout(children[i], depth + 1)
            if (result) return result
        }
        return null
    }
    function updateTouchGuard() {
        if (touchObserver.active || pullDown.active) {
            restoreHold.stop()
            suppressHoldEditing = true
        } else if (suppressHoldEditing) {
            restoreHold.restart()
        }
    }
    Binding {
        // Observe the press before it reaches the desktop's C++ filter, so
        // it cannot arm a long-press timer which outlives DragHandler's grab.
        // Keep this policy through the hold interval, then restore its binding.
        target: root.desktopLayout
        property: "editModeCondition"
        value: 0 // ContainmentLayoutManager.AppletsLayout.Locked
        when: root.desktopLayout !== null && root.suppressHoldEditing
        restoreMode: Binding.RestoreBindingOrValue
    }
    Timer {
        id: findLayout
        interval: 250
        repeat: true
        running: region.parent !== null && root.desktopLayout === null
        onTriggered: {
            root.desktopLayout = root.findDesktopLayout(region.parent, 0)
            if (root.desktopLayout) console.info("SHENG_DESKTOP_HOLD_GUARD_READY", root.nativeHoldInterval)
        }
    }
    Timer {
        id: restoreHold
        interval: Math.max(500, root.nativeHoldInterval + 120)
        onTriggered: if (!touchObserver.active && !pullDown.active) root.suppressHoldEditing = false
    }
    P5Support.DataSource {
        id: execute
        engine: "executable"
        connectedSources: []
        onNewData: function(source, data) { disconnectSource(source) }
    }
    Item {
        id: region
        parent: root.Window.window ? root.Window.window.contentItem : null
        visible: !Plasmoid.containment.corona.editMode
        x: 0
        y: 0
        width: parent ? parent.width : 0
        height: parent ? parent.height : 0
        z: 100000
        PointHandler {
            id: touchObserver
            target: null
            acceptedDevices: PointerDevice.TouchScreen
            // Observe from press without stealing normal desktop taps.
            onActiveChanged: root.updateTouchGuard()
        }
        DragHandler {
            id: pullDown
            property string qualified: ""
            target: null
            acceptedDevices: PointerDevice.TouchScreen
            minimumPointCount: 1
            maximumPointCount: 1
            dragThreshold: root.touchDragThreshold
            onActiveChanged: {
                root.updateTouchGuard()
                if (active) qualified = ""
                else if (qualified !== "") {
                    var action = qualified
                    qualified = ""
                    execute.connectSource("qdbus6 org.sheng.DesktopPolicy /org/sheng/DesktopPolicy org.sheng.DesktopPolicy." + action)
                }
            }
            onCanceled: qualified = ""
            onActiveTranslationChanged: if (active) {
                var dx = activeTranslation.x
                var dy = activeTranslation.y
                if (dy < -56 && -dy > Math.abs(dx) * 1.25) qualified = "OpenAppDrawer"
                else if (!Plasmoid.configuration.pointerPresent && centroid.scenePressPosition.x > region.width / 2 && dy > 56 && dy > Math.abs(dx) * 1.25) qualified = "OpenControlCenter"
                else qualified = ""
            }
        }
    }
}
