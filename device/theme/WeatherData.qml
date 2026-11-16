// SPDX-License-Identifier: GPL-3.0-or-later
// Keep verified weather across transient network errors and desktop restarts.
import QtQuick
import org.kde.plasma.plasmoid
Item {
    id: weather
    property real temperaturaActual: NaN
    property string iconWeatherCurrent: "weather-none-available"
    property string datosweather: ""
    property double updatedAt: 0
    property bool requestFailed: false
    property bool stale: false
    readonly property bool hasData: isFinite(temperaturaActual) && updatedAt > 0
    readonly property string statusText: hasData
        ? (stale ? "上次获取的天气 · " : "天气获取于 ") + Qt.formatDateTime(new Date(updatedAt), "MM-dd HH:mm")
        : "天气暂不可用，正在重试"
    property int requestId: 0
    property int failures: 0
    property var pendingRequest: null
    property var pendingFinish: null
    property var coordinates: null
    readonly property string locationKey: [Plasmoid.configuration.useCoordinatesIp,
        Plasmoid.configuration.latitudeC, Plasmoid.configuration.longitudeC].join(",")
    property string configurationKey: locationKey + "," + Plasmoid.configuration.temperatureUnit
    function getJson(url, callback) {
        if (pendingRequest) pendingRequest.abort()
        const request = new XMLHttpRequest()
        let finished = false
        function finish(data) {
            if (finished) return
            finished = true
            requestTimeout.stop()
            pendingRequest = null
            pendingFinish = null
            callback(data)
        }
        pendingRequest = request
        pendingFinish = finish
        request.open("GET", url)
        request.onreadystatechange = function() {
            if (request.readyState !== XMLHttpRequest.DONE) return
            if (request.status !== 200) { finish(null); return }
            let data = null
            try { data = JSON.parse(request.responseText) } catch (error) {}
            finish(data)
        }
        requestTimeout.restart()
        request.send()
    }
    function icon(code, day) {
        if (code === 0) return day ? "weather-clear" : "weather-clear-night"
        if (code <= 2) return day ? "weather-few-clouds" : "weather-few-clouds-night"
        if (code === 3) return "weather-clouds"
        if (code <= 48) return "weather-fog"
        if (code >= 95) return "weather-storm"
        if ((code >= 71 && code <= 77) || code >= 85) return "weather-snow"
        return "weather-showers"
    }
    function display(data) {
        temperaturaActual = Number(Plasmoid.configuration.temperatureUnit) === 0 ? data.celsius : data.celsius * 9 / 5 + 32
        iconWeatherCurrent = icon(data.code, data.day)
        updatedAt = data.time
        datosweather = temperaturaActual + " 0 0 " + data.code
        stale = requestFailed || Date.now() - updatedAt > 1800000
    }
    function restoreCache() {
        try {
            const data = JSON.parse(Plasmoid.configuration.weatherCache || "")
            if (data.location === locationKey && typeof data.celsius === "number" && isFinite(data.celsius) && data.time > 0) {
                display(data)
                return
            }
        } catch (error) {}
        temperaturaActual = NaN
        updatedAt = 0
        datosweather = ""
    }
    function failed() {
        requestFailed = true
        stale = true
        failures = Math.min(6, failures + 1)
        retry.interval = Math.min(300000, 15000 * Math.pow(2, failures - 1))
        retry.restart()
    }
    function forecast(latitude, longitude, id) {
        if (!isFinite(latitude) || !isFinite(longitude)) { failed(); return }
        coordinates = {latitude: latitude, longitude: longitude}
        const url = "https://api.open-meteo.com/v1/forecast?latitude=" + latitude
            + "&longitude=" + longitude + "&current=temperature_2m,weather_code,is_day&timezone=auto"
        getJson(url, function(data) {
            if (id !== requestId) return
            if (!data || !data.current || typeof data.current.temperature_2m !== "number" || !isFinite(data.current.temperature_2m)) { failed(); return }
            requestFailed = false
            failures = 0
            retry.stop()
            const current = data.current
            const saved = {location: locationKey, celsius: current.temperature_2m,
                           code: current.weather_code, day: current.is_day === 1, time: Date.now()}
            display(saved)
            // IP-derived coordinates stay in memory; the cache holds weather only.
            Plasmoid.configuration.weatherCache = JSON.stringify(saved)
        })
    }
    function refresh() {
        const id = ++requestId
        retry.stop()
        const latitude = Number(Plasmoid.configuration.latitudeC)
        const longitude = Number(Plasmoid.configuration.longitudeC)
        if (!Plasmoid.configuration.useCoordinatesIp && (latitude !== 0 || longitude !== 0)) {
            forecast(latitude, longitude, id)
            return
        }
        getJson("https://get.geojs.io/v1/ip/geo.json", function(data) {
            if (id !== requestId) return
            if (data && data.latitude && data.longitude) forecast(Number(data.latitude), Number(data.longitude), id)
            else if (coordinates) forecast(coordinates.latitude, coordinates.longitude, id)
            else failed()
        })
    }
    onConfigurationKeyChanged: initialUpdate.restart()
    Component.onCompleted: initialUpdate.restart()
    Timer { id: initialUpdate; interval: 250; onTriggered: { weather.coordinates = null; weather.restoreCache(); weather.refresh() } }
    Timer { id: retry; onTriggered: weather.refresh() }
    Timer {
        id: requestTimeout; interval: 12000
        onTriggered: {
            const finish = weather.pendingFinish
            const request = weather.pendingRequest
            if (request) request.abort()
            if (finish) finish(null)
        }
    }
    Timer { interval: 900000; running: true; repeat: true; onTriggered: weather.refresh() }
    Timer { interval: 60000; running: true; repeat: true; onTriggered: weather.stale = weather.requestFailed || Date.now() - weather.updatedAt > 1800000 }
}
