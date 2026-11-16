import QtQuick
QtObject {
    property bool darkMode: false
    readonly property color panel: darkMode ? "#f1172030" : "#faf5f7fc"
    readonly property color card: darkMode ? "#293344" : "#e5ebf4"
    readonly property color text: darkMode ? "#f5f8ff" : "#1b2940"
    readonly property color muted: darkMode ? "#afbed3" : "#64758d"
    readonly property color active: "#327dff"
    readonly property color activeText: "#ffffff"
    readonly property color activeMuted: "#d4e1f5"
    readonly property color border: darkMode ? "#30ffffff" : "#18364969"
    readonly property color sliderBase: darkMode ? "#1f3f6e" : "#cbdaee"
    readonly property color sliderFill: darkMode ? "#d4f0ff" : "#ffffff"
    readonly property color sliderInk: darkMode ? "#265a91" : "#286adb"
    readonly property color readout: darkMode ? "#88314e73" : "#dddae6f6"
}
