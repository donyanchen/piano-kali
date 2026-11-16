/*
    SPDX-FileCopyrightText: 2026 Petexy
    SPDX-FileCopyrightText: 2026 Sheng Kali contributors
    SPDX-License-Identifier: GPL-3.0-or-later

    Linexin's running-app Dock, extracted from DashboardRepresentation.qml
    into its compact panel representation. Adds persisted desktop launchers.
*/
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.kicker as Kicker
import org.kde.taskmanager as TaskManager
import "code/icons.js" as Icons

Item {
    id: root
    readonly property int dockIconSize: Math.max(32,Math.min(48,height-20))
    readonly property int dockCellSize: dockIconSize+Kirigami.Units.largeSpacing
    readonly property int hoverDuration: Math.max(0,Plasmoid.configuration.hoverEffectDuration)
    implicitWidth: Math.min(1100,appsRow.implicitWidth+Kirigami.Units.largeSpacing*2)
    implicitHeight: 84
    Layout.minimumWidth: implicitWidth
    Layout.preferredWidth: implicitWidth
    Layout.maximumWidth: implicitWidth
    Layout.minimumHeight: 64
    Layout.preferredHeight: 84
    Layout.fillWidth: false
    signal drawerRequested()
    signal appActivated()
    property alias taskRepeater: runningRepeater
    function toggleDrawer() { drawerRequested() }
    TaskManager.TasksModel {
        id: runningTasksModel
        sortMode: TaskManager.TasksModel.SortManual
        groupMode: TaskManager.TasksModel.GroupApplications
        groupInline: false
        launchInPlace: true
        separateLaunchers: false
        filterByVirtualDesktop: false
        filterByScreen: false
        filterByActivity: false
        launcherList: Plasmoid.configuration.launchers
        onLauncherListChanged: {
            if(JSON.stringify(launcherList)!==JSON.stringify(Plasmoid.configuration.launchers))Plasmoid.configuration.launchers=launcherList
        }
    }
    Rectangle {
        anchors.fill:parent
        color:Kirigami.Theme.backgroundColor
        radius:16;opacity:0.55
        Behavior on width { NumberAnimation{duration:200;easing.type:Easing.OutBack;easing.overshoot:1.1} }
    }
    Flickable {
        anchors.fill:parent;anchors.margins:Kirigami.Units.smallSpacing
        contentWidth:appsRow.implicitWidth;contentHeight:height
        flickableDirection:Flickable.HorizontalFlick;clip:true;boundsBehavior:Flickable.StopAtBounds
        Row {
            id:appsRow;anchors.verticalCenter:parent.verticalCenter
            spacing:Kirigami.Units.smallSpacing
            x:Math.max(0,(root.width-width)/2-Kirigami.Units.smallSpacing)
            Repeater {
                id:runningRepeater
                model:runningTasksModel
                delegate:Item {
                    id:task
                    required property int index
                    required property var model
                    width:root.dockCellSize;height:root.dockCellSize
                    activeFocusOnTab:true
                    Accessible.role:Accessible.Button
                    Accessible.name:model.AppName||model.display||""
                    function activate(){
                        var idx=runningTasksModel.index(index,0)
                        if(model.IsLauncher)runningTasksModel.requestNewInstance(idx)
                        else if(model.IsActive)runningTasksModel.requestToggleMinimized(idx)
                        else runningTasksModel.requestActivate(idx)
                        root.appActivated()
                    }
                    function context(){
                        dockContext.taskIndex=runningTasksModel.index(index,0)
                        dockContext.taskRow=index
                        dockContext.isWindow=model.IsWindow||model.IsGroupParent
                        dockContext.minimized=!!model.IsMinimized
                        dockContext.maximized=!!model.IsMaximized
                        dockContext.above=!!model.IsKeepAbove
                        dockContext.below=!!model.IsKeepBelow
                        dockContext.fullScreen=!!model.IsFullScreen
                        dockContext.launcher=String(model.LauncherUrlWithoutIcon||model.LauncherUrl||"")
                        dockContext.visualParent=task
                        menuOpen.restart()
                    }
                    Kirigami.Icon {
                        anchors.centerIn:parent;width:root.dockIconSize;height:width
                        source:task.model.decoration;animated:false
                        Rectangle {
                            visible:!task.model.IsLauncher
                            anchors.horizontalCenter:parent.horizontalCenter;anchors.top:parent.bottom;anchors.topMargin:2
                            width:task.model.IsActive?12:5;height:5;radius:2.5
                            color:Kirigami.Theme.highlightColor
                        }
                    }
                    Rectangle {
                        anchors.centerIn:parent;width:root.dockIconSize+Kirigami.Units.smallSpacing*2;height:width;radius:width/4
                        color:Qt.alpha(Kirigami.Theme.highlightColor,0.22)
                        border.width:2;border.color:Kirigami.Theme.focusColor
                        visible:task.activeFocus;z:-1
                    }
                    scale:runMA.pressed?0.88:(runMA.containsMouse||activeFocus)?1.08:1
                    Behavior on scale {NumberAnimation{duration:root.hoverDuration;easing.type:Easing.OutBack;easing.overshoot:2}}
                    PlasmaComponents.ToolTip.text:model.AppName||model.display||""
                    PlasmaComponents.ToolTip.visible:runMA.containsMouse
                    PlasmaComponents.ToolTip.delay:500
                    Keys.onReturnPressed:activate()
                    Keys.onEnterPressed:activate()
                    Keys.onSpacePressed:activate()
                    Keys.onPressed: event=>{if(event.key===Qt.Key_Menu){event.accepted=true;context()}}
                    MouseArea {
                        id:runMA;anchors.fill:parent;hoverEnabled:true;cursorShape:Qt.PointingHandCursor
                        acceptedButtons:Qt.LeftButton|Qt.MiddleButton|Qt.RightButton
                        onClicked:mouse=>{
                            if(mouse.button===Qt.RightButton)task.context()
                            else if(mouse.button===Qt.MiddleButton)runningTasksModel.requestNewInstance(runningTasksModel.index(task.index,0))
                            else task.activate()
                        }
                        onPressAndHold:task.context()
                    }
                }
            }
            Item {
                id:drawerButton;width:root.dockCellSize;height:root.dockCellSize
                Accessible.name:"应用抽屉";Accessible.role:Accessible.Button
                Kirigami.Icon{anchors.centerIn:parent;width:root.dockIconSize-6;height:width;source:Qt.resolvedUrl("../icons/sheng-apps-grid.svg");isMask:true;color:Kirigami.Theme.textColor;animated:false}
                scale:drawerMouse.pressed?0.88:drawerMouse.containsMouse?1.08:1
                Behavior on scale{NumberAnimation{duration:root.hoverDuration;easing.type:Easing.OutBack;easing.overshoot:2}}
                MouseArea{id:drawerMouse;anchors.fill:parent;hoverEnabled:true;onClicked:root.toggleDrawer()}
                PlasmaComponents.ToolTip.text:"应用抽屉"
                PlasmaComponents.ToolTip.visible:drawerMouse.containsMouse
            }
        }
    }
    Timer{id:menuOpen;interval:16;onTriggered:if(dockContext.visualParent&&root.visible)dockContext.open(0,-8)}
    function launcherKey(value){try{return decodeURIComponent(String(value).split("?")[0])}catch(e){return String(value).split("?")[0]}}
    function pinned(url){var list=runningTasksModel.launcherList;for(var i=0;i<list.length;i++)if(launcherKey(list[i])===launcherKey(url))return true;return false}
    function togglePin(url){
        if(!url)return
        var list=Array.from(runningTasksModel.launcherList);var at=-1
        for(var i=0;i<list.length;i++)if(launcherKey(list[i])===launcherKey(url)){at=i;break}
        if(at>=0)list.splice(at,1);else list.push(url)
        runningTasksModel.launcherList=list;Plasmoid.configuration.launchers=list
    }
    PlasmaExtras.Menu {
        id:dockContext
        property var taskIndex:null
        property int taskRow:-1
        property bool isWindow:false
        property bool minimized:false
        property bool maximized:false
        property bool above:false
        property bool below:false
        property bool fullScreen:false
        property string launcher:""
        PlasmaExtras.MenuItem{text:"打开新窗口";icon:"window-new";onClicked:runningTasksModel.requestNewInstance(dockContext.taskIndex)}
        PlasmaExtras.MenuItem{text:root.pinned(dockContext.launcher)?"取消固定到 Dock":"固定到 Dock";icon:"window-pin";visible:dockContext.launcher!=="";onClicked:root.togglePin(dockContext.launcher)}
        PlasmaExtras.MenuItem{separator:true}
        PlasmaExtras.MenuItem{text:dockContext.minimized?"恢复窗口":"最小化";icon:"window-minimize";visible:dockContext.isWindow;onClicked:runningTasksModel.requestToggleMinimized(dockContext.taskIndex)}
        PlasmaExtras.MenuItem{text:dockContext.maximized?"还原大小":"最大化";icon:"window-maximize";visible:dockContext.isWindow;onClicked:runningTasksModel.requestToggleMaximized(dockContext.taskIndex)}
        PlasmaExtras.MenuItem{text:"窗口置顶";checkable:true;checked:dockContext.above;visible:dockContext.isWindow;onClicked:runningTasksModel.requestToggleKeepAbove(dockContext.taskIndex)}
        PlasmaExtras.MenuItem{text:"窗口置底";checkable:true;checked:dockContext.below;visible:dockContext.isWindow;onClicked:runningTasksModel.requestToggleKeepBelow(dockContext.taskIndex)}
        PlasmaExtras.MenuItem{text:"全屏";checkable:true;checked:dockContext.fullScreen;visible:dockContext.isWindow;onClicked:runningTasksModel.requestToggleFullScreen(dockContext.taskIndex)}
        PlasmaExtras.MenuItem{separator:true}
        PlasmaExtras.MenuItem{text:"向左移动";enabled:dockContext.taskRow>0;onClicked:{runningTasksModel.move(dockContext.taskRow,dockContext.taskRow-1);runningTasksModel.syncLaunchers()}}
        PlasmaExtras.MenuItem{text:"向右移动";enabled:dockContext.taskRow<runningTasksModel.count-1;onClicked:{runningTasksModel.move(dockContext.taskRow,dockContext.taskRow+1);runningTasksModel.syncLaunchers()}}
        PlasmaExtras.MenuItem{text:"关闭窗口";icon:"window-close";visible:dockContext.isWindow;onClicked:runningTasksModel.requestClose(dockContext.taskIndex)}
    }
}
