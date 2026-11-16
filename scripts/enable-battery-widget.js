// Run through org.kde.PlasmaShell.evaluateScript as the desktop user.
// Reuse an existing battery applet; keep the rest of the panel layout intact.
var panelList = panels();
if (!panelList.length) throw new Error("No Plasma panel found");
var panel = panelList[0];
var widgets = panel.widgets();
var battery = null;
var clock = null;
for (var i = 0; i < widgets.length; ++i) {
    if (widgets[i].type === "org.kde.plasma.battery") battery = widgets[i];
    if (widgets[i].type === "org.kde.plasma.digitalclock") clock = widgets[i];
}
if (!battery) battery = panel.addWidget("org.kde.plasma.battery");
if (!battery) throw new Error("Battery applet could not be loaded");
battery.currentConfigGroup = ["General"];
battery.writeConfig("showPercentage", true);
battery.reloadConfig();
if (clock && clock.index >= 0) battery.index = clock.index;
print(JSON.stringify({panel: panel.id, battery: battery.id, plugin: battery.type,
                      showPercentage: battery.readConfig("showPercentage"), index: battery.index}));
