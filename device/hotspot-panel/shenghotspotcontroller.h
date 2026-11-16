// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QFileSystemWatcher>
#include <QTimer>
#include <qqmlregistration.h>

class ShengHotspotController : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(bool available READ available CONSTANT)
    Q_PROPERTY(bool hotspotSupported READ hotspotSupported NOTIFY stateChanged)
    Q_PROPERTY(bool hotspotActive READ hotspotActive NOTIFY stateChanged)
    Q_PROPERTY(bool busy READ busy NOTIFY stateChanged)
    Q_PROPERTY(bool wirelessEnabled READ wirelessEnabled WRITE setWirelessEnabled NOTIFY stateChanged)
public:
    explicit ShengHotspotController(QObject *parent = nullptr);
    bool available() const { return m_available; }
    bool hotspotSupported() const;
    bool hotspotActive() const { return m_active; }
    bool busy() const { return m_busy; }
    bool wirelessEnabled() const { return m_wirelessEnabled; }
    void setWirelessEnabled(bool enabled);
    Q_INVOKABLE void createHotspot() { changeHotspot(true); }
    Q_INVOKABLE void stopHotspot() { changeHotspot(false); }
Q_SIGNALS:
    void stateChanged();
private:
    void refresh();
    void changeHotspot(bool enabled);
    void fail(const QString &detail);
    bool m_available = false;
    bool m_active = false;
    bool m_busy = false;
    bool m_target = false;
    bool m_wirelessEnabled = true;
    quint64 m_operation = 0;
    QFileSystemWatcher m_watcher;
    QTimer m_timeout;
};
