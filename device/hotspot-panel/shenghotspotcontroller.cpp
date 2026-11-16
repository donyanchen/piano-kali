// SPDX-License-Identifier: GPL-3.0-or-later
#include "shenghotspotcontroller.h"
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QFile>
#include <QFileInfo>
#include <QDebug>
#include <KLocalizedString>
#include <KNotification>

static const QString readyFile = QStringLiteral("/run/sheng-hotspot/ready");

ShengHotspotController::ShengHotspotController(QObject *parent)
    : QObject(parent), m_watcher(this), m_timeout(this)
{
    QFile compatible(QStringLiteral("/proc/device-tree/compatible"));
    m_available = compatible.open(QIODevice::ReadOnly)
        && compatible.readAll().contains("xiaomi,sheng")
        && QFileInfo::exists(QStringLiteral("/etc/sheng-hotspot/settings.ini"));
    if (!m_available) return;
    connect(&m_watcher, &QFileSystemWatcher::directoryChanged, this, [this] { refresh(); });
    connect(&m_watcher, &QFileSystemWatcher::fileChanged, this, [this] { refresh(); });
    m_timeout.setSingleShot(true);
    m_timeout.setInterval(30000);
    connect(&m_timeout, &QTimer::timeout, this, [this] {
        refresh();
        if (m_busy) fail(i18n("The hotspot did not reach the requested state. Please try again."));
    });
    refresh();
}

bool ShengHotspotController::hotspotSupported() const
{
    return m_available && (m_active ||
        (m_wirelessEnabled && QFileInfo::exists(QStringLiteral("/sys/class/net/wlan0"))));
}

void ShengHotspotController::setWirelessEnabled(bool enabled)
{
    if (m_wirelessEnabled == enabled) return;
    m_wirelessEnabled = enabled;
    Q_EMIT stateChanged();
}

void ShengHotspotController::refresh()
{
    if (!m_available) return;
    // RuntimeDirectory is removed on stop and recreated on start. Watch /run
    // too, so we reconnect to the new directory after stop, failure or resume.
    const QStringList paths{QStringLiteral("/run"), QStringLiteral("/run/sheng-hotspot"), readyFile};
    for (const auto &path : paths) {
        if (QFileInfo::exists(path) && !m_watcher.files().contains(path) && !m_watcher.directories().contains(path))
            m_watcher.addPath(path);
    }
    const bool active = QFileInfo::exists(readyFile);
    bool changed = active != m_active;
    m_active = active;
    if (m_busy && m_active == m_target) {
        m_busy = false;
        m_timeout.stop();
        changed = true;
    }
    if (changed) Q_EMIT stateChanged();
}

void ShengHotspotController::changeHotspot(bool enabled)
{
    if (!m_available || (m_busy && m_target == enabled)) return;
    refresh();
    if (m_active == enabled && !m_busy) return;
    m_target = enabled;
    m_busy = true;
    const auto operation = ++m_operation;
    m_timeout.start();
    Q_EMIT stateChanged();

    auto message = QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.systemd1"),
        QStringLiteral("/org/freedesktop/systemd1"), QStringLiteral("org.freedesktop.systemd1.Manager"),
        enabled ? QStringLiteral("StartUnit") : QStringLiteral("StopUnit"));
    message.setArguments({QStringLiteral("sheng-hotspot.service"), QStringLiteral("replace")});
    message.setInteractiveAuthorizationAllowed(true);
    auto watcher = new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(message), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this, [this, operation](QDBusPendingCallWatcher *call) {
        QDBusPendingReply<QDBusObjectPath> reply = *call;
        call->deleteLater();
        if (operation != m_operation) return;
        if (reply.isError()) fail(reply.error().message());
        else refresh();
    });
}

void ShengHotspotController::fail(const QString &detail)
{
    m_busy = false;
    m_timeout.stop();
    refresh();
    Q_EMIT stateChanged();
    qWarning() << "Sheng hotspot operation failed:" << detail;
    auto notification = new KNotification(QStringLiteral("FailedToCreateHotspot"), KNotification::CloseOnTimeout, this);
    notification->setComponentName(QStringLiteral("networkmanagement"));
    notification->setTitle(i18n("Hotspot"));
    notification->setText(detail);
    notification->sendEvent();
}
