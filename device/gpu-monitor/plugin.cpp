// SPDX-License-Identifier: GPL-3.0-or-later
#include <KPluginFactory>
#include <QDateTime>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QHash>
#include <systemstats/SensorContainer.h>
#include <systemstats/SensorObject.h>
#include <systemstats/SensorPlugin.h>
#include <systemstats/SensorProperty.h>

class ShengGpuPlugin : public KSysGuard::SensorPlugin
{
    Q_OBJECT
public:
    ShengGpuPlugin(QObject *parent, const QVariantList &args) : SensorPlugin(parent, args)
    {
        QFile compatible(QStringLiteral("/proc/device-tree/compatible"));
        if (!compatible.open(QIODevice::ReadOnly) || !compatible.readAll().contains("xiaomi,sheng")) {
            return;
        }
        auto container = new KSysGuard::SensorContainer(QStringLiteral("gpu"), QStringLiteral("GPU"), this);
        for (const auto &id : {QStringLiteral("gpu0"), QStringLiteral("all")}) {
            auto object = new KSysGuard::SensorObject(id, QStringLiteral("Adreno 740（共享 RAM）"));
            container->addObject(object);
            QHash<QString, KSysGuard::SensorProperty *> properties;
            auto make = [&](const QString &key, const QString &label, KSysGuard::Unit unit) {
                auto property = new KSysGuard::SensorProperty(key, label, object);
                property->setUnit(unit);
                property->setVariantType(unit == KSysGuard::UnitInvalid ? QVariant::String : QVariant::Double);
                property->setPrefix(object->name());
                property->setMin(0);
                properties.insert(key, property);
                return property;
            };
            auto name = make(QStringLiteral("name"), QStringLiteral("名称"), KSysGuard::UnitInvalid);
            name->setValue(QStringLiteral("Qualcomm Adreno 740（统一共享内存）"));
            auto usage = make(QStringLiteral("usage"), QStringLiteral("GPU 使用率"), KSysGuard::UnitPercent);
            usage->setMax(100);
            usage->setDescription(QStringLiteral("内核 DRM fdinfo 引擎运行时间增量；按 DRM 客户端去重。"));
            auto total = make(QStringLiteral("totalVram"), QStringLiteral("可共享系统 RAM 上限"), KSysGuard::UnitByte);
            total->setDescription(QStringLiteral("GPU 与 CPU 共用物理 RAM；此值不是独立显存，也不是为 GPU 预留的内存。"));
            auto used = make(QStringLiteral("usedVram"), QStringLiteral("GPU 驻留共享图形内存"), KSysGuard::UnitByte);
            used->setMax(total);
            used->setDescription(QStringLiteral("内核 MSM GEM 全局 Resident 字节数；共享对象仅计一次，已包含在系统内存用量内。"));
            make(QStringLiteral("coreFrequency"), QStringLiteral("GPU 频率（最近设定）"), KSysGuard::UnitMegaHertz);
            make(QStringLiteral("activeMemory"), QStringLiteral("活跃图形内存"), KSysGuard::UnitByte);
            make(QStringLiteral("powerState"), QStringLiteral("GPU 电源状态"), KSysGuard::UnitInvalid);
            m_properties.append(properties);
        }
        update();
    }

    QString providerName() const override { return QStringLiteral("gpu"); }

    void update() override
    {
        QFile file(QStringLiteral("/run/sheng-gpu-monitor/metrics.json"));
        QJsonObject data;
        if (file.open(QIODevice::ReadOnly)) {
            data = QJsonDocument::fromJson(file.readAll()).object();
        }
        const qint64 timestamp = static_cast<qint64>(data.value(QStringLiteral("timestamp_ms")).toDouble());
        const qint64 age = QDateTime::currentMSecsSinceEpoch() - timestamp;
        const bool fresh = !data.isEmpty() && age >= 0 && age < 15000;
        for (const auto &properties : m_properties) {
            auto set = [&](const QString &id, const QString &key, double scale = 1.0) {
                const auto value = data.value(key);
                properties.value(id)->setValue(fresh && value.isDouble() ? QVariant(value.toDouble() / scale) : QVariant());
            };
            set(QStringLiteral("usage"), QStringLiteral("usage_percent"));
            set(QStringLiteral("totalVram"), QStringLiteral("memory_total_bytes"));
            set(QStringLiteral("usedVram"), QStringLiteral("memory_resident_bytes"));
            set(QStringLiteral("activeMemory"), QStringLiteral("memory_active_bytes"));
            set(QStringLiteral("coreFrequency"), QStringLiteral("frequency_hz"), 1000000.0);
            properties.value(QStringLiteral("powerState"))->setValue(
                fresh ? QVariant(data.value(QStringLiteral("runtime_status")).toString()) : QVariant());
        }
    }
private:
    QList<QHash<QString, KSysGuard::SensorProperty *>> m_properties;
};

K_PLUGIN_CLASS_WITH_JSON(ShengGpuPlugin, "metadata.json")
#include "plugin.moc"
