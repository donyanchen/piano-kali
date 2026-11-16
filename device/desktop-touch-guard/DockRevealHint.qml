// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick

Item {
    clip: true
    // Crop the lower half of the rounding flush with the physical bottom edge.
    Rectangle {
        width: parent.width
        height: parent.height * 2
        radius: parent.height
        color: "white"
    }
}
