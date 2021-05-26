/*
    SPDX-FileCopyrightText: 2021 Volker Krause <vkrause@kde.org>

    SPDX-License-Identifier: LGPL-2.0-or-later
*/

#include <KCountry>
#include <KCountrySubdivision>
#include <KTimeZone>

#include <QCoreApplication>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQmlExtensionPlugin>

class KI18nQmlPlugin : public QQmlExtensionPlugin
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID "org.qt-project.Qt.QQmlExtensionInterface")
public:
    void registerTypes(const char *uri) override;
};

// return "undefined" for invalid objects, so JS conditionals work as expected
template<typename T>
static QJSValue toJsValue(T value, QJSEngine *engine)
{
    return value.isValid() ? engine->toScriptValue(value) : QJSValue(QJSValue::UndefinedValue);
}

class KCountryFactory
{
    Q_GADGET
    Q_PROPERTY(QList<KCountry> allCountries READ allCountries)
public:
    Q_INVOKABLE QJSValue fromAlpha2(const QString &code) const
    {
        return toJsValue(KCountry::fromAlpha2(code), m_engine);
    }
    Q_INVOKABLE QJSValue fromAlpha3(const QString &code) const
    {
        return toJsValue(KCountry::fromAlpha3(code), m_engine);
    }
    Q_INVOKABLE QJSValue fromName(const QString &name) const
    {
        return toJsValue(KCountry::fromName(name), m_engine);
    }
    Q_INVOKABLE QJSValue fromLocation(double latitude, double longitude) const
    {
        return toJsValue(KCountry::fromLocation(latitude, longitude), m_engine);
    }

    QJSEngine *m_engine = nullptr;

private:
    QList<KCountry> allCountries() const
    {
        return KCountry::allCountries();
    }
};

class KCountrySubdivisionFactory
{
    Q_GADGET
public:
    Q_INVOKABLE QJSValue fromCode(const QString &code) const
    {
        return toJsValue(KCountrySubdivision::fromCode(code), m_engine);
    }
    Q_INVOKABLE QJSValue fromLocation(double latitude, double longitude) const
    {
        return toJsValue(KCountrySubdivision::fromLocation(latitude, longitude), m_engine);
    }

    QJSEngine *m_engine = nullptr;
};

void KI18nQmlPlugin::registerTypes(const char *)
{
    qRegisterMetaType<KCountry>();
    qRegisterMetaType<KCountrySubdivision>();
    qRegisterMetaType<QList<KCountrySubdivision>>();

    // HACK qmlplugindump chokes on gadget singletons, to the point of breaking ecm_find_qmlmodule()
    if (QCoreApplication::applicationName() != QLatin1String("qmlplugindump")) {
        qmlRegisterSingletonType("org.kde.ki18n", 1, 0, "KCountry", [](QQmlEngine *, QJSEngine *engine) -> QJSValue {
            KCountryFactory factory;
            factory.m_engine = engine;
            return engine->toScriptValue(factory);
        });
        qmlRegisterSingletonType("org.kde.ki18n", 1, 0, "KCountrySubdivision", [](QQmlEngine *, QJSEngine *engine) -> QJSValue {
            KCountrySubdivisionFactory factory;
            factory.m_engine = engine;
            return engine->toScriptValue(factory);
        });
    }
}

#include "ki18nqmlplugin.moc"
