#include <QtGui/QGuiApplication>
#include <QtGui/QScreen>
#include <QtGui/QInputDevice>
#include <QtQuick/QQuickWindow>
#include <QtQml/QQmlApplicationEngine>
#include <QtQml/QQmlContext>
#include <QtQml/qqml.h>
#include <QtCore/QTimer>
#include <QtCore/QDebug>
#include <QtCore/QSysInfo>
#include "StrokeSurface.h"
#include "TabletNavigation.h"
#include "EpaperDisplayControl.h"

int main(int argc, char **argv) {
    for (int i = 1; i < argc; ++i) {
        if (QByteArray(argv[i]) == "--probe") {
            qInfo() << "Ink standalone benchmark; compiled Qt" << QT_VERSION_STR
                    << "runtime Qt" << qVersion() << "architecture" << QSysInfo::currentCpuArchitecture();
            return 0;
        }
    }
    QCoreApplication::setAttribute(Qt::AA_SynthesizeMouseForUnhandledTabletEvents, true);
    QGuiApplication app(argc, argv);
    app.setApplicationName("Ink standalone benchmark");
    qInfo() << "Platform:" << QGuiApplication::platformName()
            << "Qt Quick backend:" << qgetenv("QT_QUICK_BACKEND");
    for (auto *screen : app.screens())
        qInfo() << "Screen:" << screen->name() << "geometry" << screen->geometry()
                << "DPR" << screen->devicePixelRatio() << "orientation" << screen->orientation();
    for (const auto *device : QInputDevice::devices())
        qInfo() << "Input:" << device->name() << device->type() << device->capabilities();
    qmlRegisterType<StrokeSurface>("Ink.Benchmark", 1, 0, "StrokeSurface");
    EpaperDisplayControl displayControl;
    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty("benchmarkFullscreen", app.arguments().contains("--fullscreen"));
    engine.rootContext()->setContextProperty("displayControl", &displayControl);
    QObject::connect(&engine, &QQmlApplicationEngine::objectCreationFailed, &app, [] {
        QCoreApplication::exit(1);
    }, Qt::QueuedConnection);
    engine.load(QUrl("qrc:/benchmark/Main.qml"));
    if (engine.rootObjects().isEmpty()) return 1;
    auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
    TabletNavigation penNavigation(window,
        engine.rootObjects().first()->findChild<QQuickItem *>("strokeSurface"));
    if (window) {
        QObject::connect(window, &QQuickWindow::afterRendering, &displayControl,
                         &EpaperDisplayControl::initialize,
                         static_cast<Qt::ConnectionType>(Qt::QueuedConnection | Qt::SingleShotConnection));
        QTimer::singleShot(1500, &displayControl, &EpaperDisplayControl::initialize);
        if (app.arguments().contains("--fullscreen") && window->screen()) {
            // Minimal embedded QPA backends need explicit geometry, not only a state hint.
            window->setGeometry(window->screen()->geometry());
            window->showFullScreen();
        }
        qInfo() << "Window geometry:" << window->geometry() << "DPR" << window->devicePixelRatio();
    }
    if (app.arguments().contains("--smoke-test")) QTimer::singleShot(500, &app, &QCoreApplication::quit);
    const int result = app.exec();
    displayControl.shutdown();
    return result;
}
