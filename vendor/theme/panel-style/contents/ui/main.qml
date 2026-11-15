// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore

PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    implicitWidth: 0
    implicitHeight: 0
    Layout.minimumWidth: 0
    Layout.maximumWidth: 0
    preferredRepresentation: fullRepresentation
    fullRepresentation: Item { implicitWidth: 0; implicitHeight: 0 }
    property var installed: []
    property var bindings: []
    Component { id: glyphComponent; BatteryGlyph {} }
    Component {
        id: hideOriginal
        Binding { property: "opacity"; value: 0; restoreMode: Binding.RestoreBindingOrValue }
    }
    function scan(item, depth) {
        if (!item || depth > 28) return
        if ("batteryPercent" in item && "batteryPluggedIn" in item && installed.indexOf(item) < 0) {
            var original = Array.from(item.children)
            for (var i = 0; i < original.length; i++)
                if ("opacity" in original[i]) bindings.push(hideOriginal.createObject(root, {target: original[i]}))
            glyphComponent.createObject(item, {battery: item})
            installed.push(item)
            console.info("SHENG_BATTERY_GLYPH_READY")
            return
        }
        var children = Array.from(item.children || [])
        for (var j = 0; j < children.length; j++) scan(children[j], depth + 1)
    }
    Timer {
        interval: 500; repeat: true; running: root.Window.window !== null
        property int attempts: 0
        onTriggered: {
            root.scan(root.Window.window.contentItem, 0)
            if (root.installed.length > 0 || ++attempts >= 20) stop()
        }
    }
    Component.onDestruction: {
        for (var i = 0; i < installed.length; i++) if (installed[i]) {
            var children = Array.from(installed[i].children)
            for (var j = 0; j < children.length; j++)
                if (children[j].objectName === "sheng-battery-glyph") children[j].destroy()
        }
    }
}
