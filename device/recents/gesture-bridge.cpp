// SPDX-License-Identifier: MIT
#include <libinput.h>
#include <libudev.h>
#include <linux/uinput.h>
#include <sys/inotify.h>
#include <sys/ioctl.h>
#include <sys/wait.h>
#include <poll.h>
#include <fcntl.h>
#include <unistd.h>
#include <grp.h>
#include <pwd.h>
#include <signal.h>
#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <map>
#include <set>
#include <string>

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;
static volatile sig_atomic_t stopping = 0;
static void stop(int) { stopping = 1; }
static int openInput(const char *path, int flags, void *) {
    const int fd = open(path, flags | O_CLOEXEC);
    return fd < 0 ? -errno : fd;
}
static void closeInput(int fd, void *) { close(fd); }
static const libinput_interface inputInterface{openInput, closeInput};

class Keys {
    int fd = -1;
    bool alt = false;
    void emitKey(int key, int value) {
        input_event events[2]{};
        events[0].type = EV_KEY;
        events[0].code = key;
        events[0].value = value;
        events[1].type = EV_SYN;
        events[1].code = SYN_REPORT;
        if (write(fd, events, sizeof(events)) != sizeof(events)) perror("uinput write");
    }
public:
    Keys() {
        fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK | O_CLOEXEC);
        if (fd < 0) { perror("open uinput"); exit(1); }
        ioctl(fd, UI_SET_EVBIT, EV_KEY);
        for (int key : {KEY_LEFTALT, KEY_LEFTSHIFT, KEY_TAB, KEY_ESC, KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN})
            ioctl(fd, UI_SET_KEYBIT, key);
        uinput_setup setup{};
        snprintf(setup.name, sizeof(setup.name), "Sheng Task Gesture Keys");
        setup.id.bustype = BUS_VIRTUAL;
        setup.id.vendor = 0x1209;
        setup.id.product = 0x5347;
        setup.id.version = 1;
        if (ioctl(fd, UI_DEV_SETUP, &setup) < 0 || ioctl(fd, UI_DEV_CREATE) < 0) {
            perror("create gesture keyboard"); exit(1);
        }
        usleep(350000); // Let udev and the compositor discover this device.
    }
    void tap(int code) { emitKey(code, 1); emitKey(code, 0); }
    void begin(bool forward) { emitKey(KEY_LEFTALT, 1); alt = true; next(forward); }
    void next(bool forward) {
        if (!forward) emitKey(KEY_LEFTSHIFT, 1);
        tap(KEY_TAB);
        if (!forward) emitKey(KEY_LEFTSHIFT, 0);
    }
    void finish(bool cancelled) {
        if (!alt) return;
        if (cancelled) tap(KEY_ESC);
        emitKey(KEY_LEFTSHIFT, 0);
        emitKey(KEY_LEFTALT, 0);
        alt = false;
    }
    ~Keys() { finish(true); if (fd >= 0) { ioctl(fd, UI_DEV_DESTROY); close(fd); } }
};

// Only fixed, registered KWin actions are invoked. No shell or command strings.
static void action(const char *name) {
    if (!fs::exists("/run/user/1000/bus")) return;
    const pid_t pid = fork();
    if (pid == 0) {
        setgroups(0, nullptr);
        if (setgid(1000) || setuid(1000)) _exit(1);
        setenv("HOME", "/home/kali", 1);
        setenv("XDG_RUNTIME_DIR", "/run/user/1000", 1);
        setenv("DBUS_SESSION_BUS_ADDRESS", "unix:path=/run/user/1000/bus", 1);
        execlp("qdbus6", "qdbus6", "org.kde.kglobalaccel", "/component/kwin",
               "org.kde.kglobalaccel.Component.invokeShortcut", name, nullptr);
        _exit(1);
    }
    if (pid > 0) { int status; while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {} }
}

class Gesture {
    Keys &keys;
    bool armed = false;
    bool switching = false;
    double x = 0, y = 0, navX = 0, navY = 0;
    Clock::time_point updated{};
    Clock::time_point started{};
    Clock::time_point selected{};
    int lastDirection = 0;
    int intent = 0; // 0 undecided, 1 horizontal, 2 vertical (ignored)
    int candidate = 0;
    Clock::time_point candidateSince{};
public:
    libinput_device *source = nullptr;
    explicit Gesture(Keys &keyboard) : keys(keyboard) {}
    void begin(libinput_device *device, int fingers) {
        end(true);
        if (fingers != 3) return;
        source = device;
        armed = true;
        x = y = navX = navY = 0;
        lastDirection = 0;
        intent = candidate = 0;
        updated = Clock::now();
        started = updated;
    }
    void update(double dx, double dy) {
        if (!armed) return;
        updated = Clock::now();
        // Reject discontinuous contact jumps without turning them into keys.
        if (std::hypot(dx, dy) > 35) return;
        x += dx; y += dy;
        if (!switching) {
            if (intent != 2 && std::abs(y) >= 12 && std::abs(y) >= std::abs(x) * 1.25) intent = 2;
            else if (!intent && std::abs(x) >= 32 && std::abs(x) >= std::abs(y) * 1.8) intent = 1;
            if (intent != 1 || std::abs(x) < std::abs(y) * 1.8
                || Clock::now() - started < std::chrono::milliseconds(60)) return;
            action("Sheng Leave Task Cards");
            keys.begin(x > 0);
            switching = true;
            navX = navY = 0;
            selected = Clock::now();
            lastDirection = x > 0 ? 1 : -1;
            puts("SHENG_NATIVE_TABBOX opened"); fflush(stdout);
            return;
        }
        // Once native Alt+Tab is open, either axis navigates its frozen MRU
        // list. Vertical movement never invokes task cards in this state.
        navX += dx; navY += dy;
        const bool horizontal = std::abs(navX) >= std::abs(navY);
        double &distance = horizontal ? navX : navY;
        const double cross = horizontal ? std::abs(navY) : std::abs(navX);
        const int direction = distance > 0 ? 1 : -1;
        const int proposed = (horizontal ? 1 : 2) * direction;
        const double threshold = proposed == -lastDirection ? 140 : 110;
        if (std::abs(distance) < 12 || std::abs(distance) < cross * 1.5) return;
        if (candidate != proposed) { candidate = proposed; candidateSince = Clock::now(); }
        if (std::abs(distance) >= threshold
            && Clock::now() - candidateSince >= std::chrono::milliseconds(100)
            && Clock::now() - selected >= std::chrono::milliseconds(180)) {
            const int key = horizontal ? (direction > 0 ? KEY_RIGHT : KEY_LEFT)
                                       : (direction > 0 ? KEY_DOWN : KEY_UP);
            keys.tap(key);
            navX = navY = 0;
            candidate = 0;
            selected = Clock::now();
            lastDirection = proposed;
            printf("SHENG_NATIVE_TABBOX navigate %s %s\n", horizontal ? "horizontal" : "vertical", direction > 0 ? "positive" : "negative");
            fflush(stdout);
        }
    }
    void end(bool cancelled) {
        if (!armed) return;
        if (switching) {
            const bool abort = cancelled || std::hypot(x, y) < 40;
            keys.finish(abort);
            printf("SHENG_NATIVE_TABBOX %s\n", abort ? "cancelled" : "accepted");
        }
        armed = switching = false;
        source = nullptr;
        fflush(stdout);
    }
    void watchdog() {
        if (armed && Clock::now() - updated > std::chrono::seconds(30)) end(true);
    }
};

int main(int argc, char **argv) {
    const bool allowTest = argc == 2 && std::string(argv[1]) == "--allow-test-device";
    signal(SIGTERM, stop); signal(SIGINT, stop);
    Keys keyboard;
    Gesture gesture(keyboard);
    udev *udevContext = udev_new();
    libinput *context = libinput_path_create_context(&inputInterface, nullptr);
    if (!context || !udevContext) return 1;
    std::map<std::string, libinput_device *> devices;
    std::set<std::string> ignored;
    auto scan = [&]() {
        std::set<std::string> present;
        std::error_code error;
        for (const auto &entry : fs::directory_iterator("/dev/input", error)) {
            const std::string node = entry.path().filename().string();
            if (node.rfind("event", 0) != 0) continue;
            const std::string path = entry.path();
            present.insert(path);
            if (devices.count(path) || ignored.count(path)) continue;
            udev_device *device = udev_device_new_from_subsystem_sysname(udevContext, "input", node.c_str());
            const char *tag = device ? udev_device_get_property_value(device, "ID_INPUT_TOUCHPAD") : nullptr;
            if (tag && std::string(tag) == "1") {
                libinput_device *input = libinput_path_add_device(context, path.c_str());
                if (input) {
                    // path_add returns a borrowed reference, valid only until
                    // dispatch. The map owns one independent reference.
                    libinput_device_ref(input);
                    const std::string name = libinput_device_get_name(input);
                    if (!allowTest && name == "Sheng Gesture Verification Touchpad") {
                        libinput_path_remove_device(input);
                        libinput_device_unref(input);
                        ignored.insert(path);
                    } else {
                        devices[path] = input;
                        printf("SHENG_GESTURE_DEVICE %s %s\n", node.c_str(), name.c_str()); fflush(stdout);
                    }
                }
            } else if (device && udev_device_get_is_initialized(device)) {
                ignored.insert(path);
            }
            if (device) udev_device_unref(device);
        }
        for (auto it = devices.begin(); it != devices.end();) {
            if (!present.count(it->first)) {
                if (gesture.source == it->second) gesture.end(true);
                libinput_path_remove_device(it->second);
                libinput_device_unref(it->second);
                it = devices.erase(it);
            } else ++it;
        }
        for (auto it = ignored.begin(); it != ignored.end();) {
            if (!present.count(*it)) it = ignored.erase(it); else ++it;
        }
    };
    const int watcher = inotify_init1(IN_NONBLOCK | IN_CLOEXEC);
    inotify_add_watch(watcher, "/dev/input", IN_CREATE | IN_DELETE | IN_ATTRIB);
    scan();
    pollfd fds[] = {{libinput_get_fd(context), POLLIN, 0}, {watcher, POLLIN, 0}};
    while (!stopping) {
        const int ready = poll(fds, 2, 1000);
        if (ready < 0 && errno != EINTR) break;
        if (fds[1].revents & POLLIN) {
            char buffer[4096];
            while (read(watcher, buffer, sizeof(buffer)) > 0) {}
            usleep(60000);
            scan();
        }
        libinput_dispatch(context);
        bool rescan = false;
        while (libinput_event *event = libinput_get_event(context)) {
            const auto type = libinput_event_get_type(event);
            if (type == LIBINPUT_EVENT_GESTURE_SWIPE_BEGIN) {
                auto *swipe = libinput_event_get_gesture_event(event);
                gesture.begin(libinput_event_get_device(event), libinput_event_gesture_get_finger_count(swipe));
            } else if (type == LIBINPUT_EVENT_GESTURE_SWIPE_UPDATE) {
                auto *swipe = libinput_event_get_gesture_event(event);
                if (gesture.source == libinput_event_get_device(event))
                    gesture.update(libinput_event_gesture_get_dx_unaccelerated(swipe), libinput_event_gesture_get_dy_unaccelerated(swipe));
            } else if (type == LIBINPUT_EVENT_GESTURE_SWIPE_END) {
                auto *swipe = libinput_event_get_gesture_event(event);
                if (gesture.source == libinput_event_get_device(event))
                    gesture.end(libinput_event_gesture_get_cancelled(swipe));
            } else if (type == LIBINPUT_EVENT_DEVICE_REMOVED) {
                libinput_device *removed = libinput_event_get_device(event);
                if (gesture.source == removed) gesture.end(true);
                for (auto it = devices.begin(); it != devices.end();) {
                    if (it->second == removed) {
                        libinput_device_unref(it->second);
                        it = devices.erase(it);
                    } else ++it;
                }
                rescan = true;
            }
            libinput_event_destroy(event);
        }
        if (rescan) scan();
        gesture.watchdog();
    }
    gesture.end(true);
    for (auto &[path, input] : devices) {
        libinput_path_remove_device(input);
        libinput_device_unref(input);
    }
    close(watcher);
    libinput_unref(context);
    udev_unref(udevContext);
}
