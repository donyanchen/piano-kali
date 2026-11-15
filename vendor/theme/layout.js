// Article-inspired layout; keep the existing task manager, tray and battery.
var list = panels();
var dock = null;
for (var p of list) {
    p.currentConfigGroup = ["General"];
    if (p.readConfig("ShengThemeRole", "") === "top") throw new Error("Theme layout already exists");
    if (p.widgets().some(w => w.type === "org.kde.plasma.icontasks")) dock = p;
}
if (!dock) throw new Error("Existing task manager panel not found");
var old = dock.widgets();
function existing(type) { return old.find(w => w.type === type); }
var top = new Panel;
top.location = "top";
top.height = 40;
top.hiding = "none";
top.alignment = "left";
top.lengthMode = "fill";
top.currentConfigGroup = ["General"];
top.writeConfig("ShengThemeRole", "top");
function use(type) {
    var widget = existing(type);
    return widget ? top.addWidget(widget) : top.addWidget(type);
}
var kickoff = use("org.kde.plasma.kickoff");
kickoff.currentConfigGroup = ["General"];
kickoff.writeConfig("icon", "start-here-kde-symbolic");
var windowList = top.addWidget("org.kde.plasma.windowlist");
var globalMenu = top.addWidget("org.kde.plasma.appmenu");
var spacerLeft = top.addWidget("org.kde.plasma.panelspacer");
var clock = use("org.kde.plasma.digitalclock");
clock.currentConfigGroup = ["Appearance"];
clock.writeConfig("showDate", true);
clock.writeConfig("dateFormat", "custom");
clock.writeConfig("customDateFormat", "MM-dd");
clock.writeConfig("showSeconds", 2);
clock.writeConfig("dateDisplayFormat", 2);
clock.writeConfig("autoFontAndSize", true);
clock.writeConfig("use24hFormat", 2);
clock.reloadConfig();
var spacerRight = top.addWidget("org.kde.plasma.panelspacer");
var tray = use("org.kde.plasma.systemtray");
var battery = use("org.kde.plasma.battery");
battery.currentConfigGroup = ["General"];
battery.writeConfig("showPercentage", true);
battery.reloadConfig();
var topColorizer = top.addWidget("luisbocanegra.panel.colorizer");
topColorizer.currentConfigGroup = ["General"];
topColorizer.writeConfig("hideWidget", true);
topColorizer.writeConfig("isEnabled", true);
topColorizer.reloadConfig();

dock.location = "bottom";
dock.height = 84;
dock.hiding = "windowsgobelow";
dock.alignment = "center";
dock.minimumLength = 1;
dock.maximumLength = 1100;
dock.lengthMode = "fit";
dock.currentConfigGroup = ["General"];
dock.writeConfig("ShengThemeRole", "dock");
for (var widget of dock.widgets()) {
    if (widget.type !== "org.kde.plasma.icontasks") widget.remove();
}
var tasks = dock.widgets("org.kde.plasma.icontasks")[0];
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("fill", false);
tasks.writeConfig("maxStripes", 1);
var launchers = tasks.readConfig("launchers", []);
if (typeof launchers === "string") launchers = launchers.split(",");
launchers = Array.from(launchers);
for (var launcher of ["applications:systemsettings.desktop"]) {
    if (launchers.indexOf(launcher) < 0) launchers.push(launcher);
}
tasks.writeConfig("launchers", launchers);
tasks.reloadConfig();
var dockColorizer = dock.addWidget("luisbocanegra.panel.colorizer");
dockColorizer.currentConfigGroup = ["General"];
dockColorizer.writeConfig("hideWidget", true);
dockColorizer.writeConfig("isEnabled", true);
dockColorizer.reloadConfig();

var desktop = desktops()[0];
var redmi = desktop.addWidget("Redmi.Clock", 32, 104, 304, 304);
redmi.currentConfigGroup = ["General"];
redmi.writeConfig("colorHex", "#ffffff");
redmi.writeConfig("boldfonts", false);
redmi.reloadConfig();
desktop.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
desktop.writeConfig("Image", "file:///home/kali/.local/share/wallpapers/Miku-White-Dress-4K.jpg");
desktop.writeConfig("FillMode", 2);
desktop.reloadConfig();
print(JSON.stringify({top: top.id, dock: dock.id, topColorizer: topColorizer.id,
    dockColorizer: dockColorizer.id, clock: redmi.id, tray: tray.id, battery: battery.id,
    topOrder: [kickoff.id, windowList.id, globalMenu.id, spacerLeft.id, clock.id,
        spacerRight.id, tray.id, battery.id, topColorizer.id]}));
