#include "EpaperDisplayControl.h"
#include <QtCore/QCryptographicHash>
#include <QtCore/QFile>
#include <QtCore/QMetaEnum>
#include <QtCore/QThread>
#include <QtCore/QDebug>
#include <QtGui/QGuiApplication>

EpaperDisplayControl::EpaperDisplayControl(QObject *parent) : QObject(parent) {
    m_cleanup.setSingleShot(true);
    m_cleanup.setInterval(700);
    connect(&m_cleanup, &QTimer::timeout, this, &EpaperDisplayControl::cleanNow);
    qRegisterMetaType<EPScreenMode>("EPScreenMode");
}
void EpaperDisplayControl::fail(const QString &message) {
    m_status = message; qWarning().noquote() << message; emit changed();
}
void EpaperDisplayControl::initialize() {
    if (m_attempted) return;
    m_attempted = true;
    if (QGuiApplication::platformName() != "epaper") {
        fail("Display controls: desktop preview"); return;
    }
    const QString path = "/usr/lib/plugins/scenegraph/libqsgepaper.so";
    QFile file(path);
    QCryptographicHash hash(QCryptographicHash::Sha256);
    if (!file.open(QIODevice::ReadOnly) || !hash.addData(&file)) {
        fail("Display controls: could not identify epaper library"); return;
    }
    if (hash.result().toHex() != "07aa9327f725288a5df5aebc33ea4b151c27d97d3b850279947ddddf3dd8ddec") {
        fail("Display controls: unverified library version; unchanged"); return;
    }
    m_library.setFileName(path);
    m_library.setLoadHints(QLibrary::PreventUnloadHint);
    if (!m_library.load()) { fail("Display controls: library unavailable"); return; }
    // Inspect actual loaded Qt metadata before invoking any control methods.
    auto *meta = reinterpret_cast<const QMetaObject *>(
        m_library.resolve("_ZN16EPScreenModeItem16staticMetaObjectE"));
    if (!meta || meta->indexOfEnumerator("Mode") < 0) {
        fail("Display controls: mode metadata unavailable"); return;
    }
    const auto mode = meta->enumerator(meta->indexOfEnumerator("Mode"));
    if (mode.keyToValue("Pen") != 0 || mode.keyToValue("Animation") != 2 || mode.keyToValue("UI") != 3) {
        fail("Display controls: mode metadata differs; unchanged"); return;
    }
    // Captured export is a static singleton accessor; EPFramebuffer derives QObject.
    // No object allocation, private field offsets or framebuffer memory are used.
    using Instance = QObject *(*)();
    const auto instance = reinterpret_cast<Instance>(m_library.resolve("_ZN13EPFramebuffer8instanceEv"));
    if (!instance || !attachBackend(instance())) fail("Display controls: unsupported backend interface/thread");
}
bool EpaperDisplayControl::attachBackend(QObject *backend) {
    if (!backend || backend->thread() != QThread::currentThread()) return false;
    for (const char *method : {"pushGlobalScreenMode(EPScreenMode)", "popGlobalScreenMode()", "clearGhosting()"})
        if (backend->metaObject()->indexOfMethod(method) < 0) return false;
    m_backend = backend;
    applyMode();
    requestCleanup();
    return true;
}
bool EpaperDisplayControl::popMode() {
    if (!m_pushed) return true;
    if (!m_backend || !QMetaObject::invokeMethod(m_backend, "popGlobalScreenMode", Qt::DirectConnection)) {
        fail("Display controls: mode restore failed"); return false;
    }
    m_pushed = false;
    return true;
}
void EpaperDisplayControl::applyMode() {
    if (!m_backend) return;
    if (!m_enabled || (m_canvas && !m_canvasPenMode)) {
        if (!popMode()) return;
        const QString status = m_enabled && m_canvas ? "Display policy: default canvas" : "Display policy: default";
        if (m_status != status) { m_status = status; emit changed(); }
        return;
    }
    const EPScreenMode desired = (m_canvas || m_ink) ? EPScreenMode::Pen : m_motion ? EPScreenMode::Animation : EPScreenMode::UI;
    if (m_pushed && desired == m_mode) return;
    if (!popMode()) return;
    if (!QMetaObject::invokeMethod(m_backend, "pushGlobalScreenMode", Qt::DirectConnection,
                                  Q_ARG(EPScreenMode, desired))) {
        fail("Display controls: mode selection failed"); return;
    }
    m_pushed = true; m_mode = desired;
    const QString mode = (m_canvas || m_ink) ? "Pen" : m_motion ? "Animation" : "UI";
    m_status = "Display policy: " + mode;
    qInfo().noquote() << m_status;
    emit changed();
}
void EpaperDisplayControl::setEnabled(bool enabled) {
    if (m_enabled == enabled) return;
    m_enabled = enabled;
    m_cleanup.stop();
    applyMode();
    if (enabled) requestCleanup();
    emit changed();
}
void EpaperDisplayControl::setMotionActive(bool active) {
    m_motion = active;
    if (active) m_cleanup.stop();
    applyMode();
    if (!active) requestCleanup();
}
void EpaperDisplayControl::setInkActive(bool active) {
    if (m_ink == active) return;
    m_ink = active;
    if (m_canvas) return; // No policy/refresh work in the original canvas's pen path.
    if (active) m_cleanup.stop();
    applyMode();
    if (!active) requestCleanup();
}
void EpaperDisplayControl::setCanvasPenMode(bool enabled) {
    if (m_canvasPenMode == enabled || m_ink) return;
    m_canvasPenMode = enabled;
    m_cleanup.stop();
    applyMode();
    emit changed();
}
void EpaperDisplayControl::setCanvasActive(bool active) {
    if (m_canvas == active) return;
    m_canvas = active;
    m_cleanup.stop();
    m_motion = false;
    if (!active) m_ink = false;
    // Select one policy for the entire canvas session, never per stroke.
    applyMode();
    if (!active) requestCleanup();
}
void EpaperDisplayControl::requestCleanup() {
    if (m_backend && m_enabled && !m_canvas && !m_motion && !m_ink) m_cleanup.start();
}
void EpaperDisplayControl::cleanNow() {
    m_cleanup.stop();
    if (!m_backend || !m_enabled || m_motion || m_ink) return;
    if (!QMetaObject::invokeMethod(m_backend, "clearGhosting", Qt::DirectConnection))
        fail("Display controls: cleanup invocation failed");
    else qInfo() << "Display: requested hardware ghost cleanup";
}
void EpaperDisplayControl::shutdown() {
    m_cleanup.stop(); popMode(); m_backend = nullptr;
}
