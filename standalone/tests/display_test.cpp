#include "EpaperDisplayControl.h"
#include "DisplayTestBackend.h"
#include <QtCore/QCoreApplication>
#include <QtCore/QEventLoop>
#include <QtCore/QDebug>

class TestControl : public EpaperDisplayControl {
public:
    using EpaperDisplayControl::attachBackend;
};
int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    DisplayTestBackend backend;
    TestControl control;
    if (!control.attachBackend(&backend) || backend.stack != QVector<EPScreenMode>{EPScreenMode::UI}) return 1;
    for (int i = 0; i < 10; ++i) control.setMotionActive(true);
    if (backend.stack != QVector<EPScreenMode>{EPScreenMode::Animation}) return 2;
    control.cleanNow();
    if (backend.cleanups) return 3; // Never clean during interaction.
    control.setInkActive(true);
    control.setMotionActive(false);
    if (backend.stack != QVector<EPScreenMode>{EPScreenMode::Pen}) return 4;
    control.setInkActive(false);
    if (backend.stack != QVector<EPScreenMode>{EPScreenMode::UI}) return 5;
    control.setEnabled(false);
    control.cleanNow();
    if (!backend.stack.isEmpty() || backend.cleanups) return 6;
    control.setEnabled(true);
    control.requestCleanup();
    QEventLoop wait;
    QTimer::singleShot(1000, &wait, &QEventLoop::quit);
    wait.exec();
    if (backend.cleanups != 1) return 7;
    control.setCanvasActive(true);
    if (backend.stack != QVector<EPScreenMode>{EPScreenMode::Pen}) return 10;
    const int pushes = backend.pushes, pops = backend.pops;
    int statusChanges = 0;
    QObject::connect(&control, &EpaperDisplayControl::changed, &app, [&] { ++statusChanges; });
    for (int i = 0; i < 20; ++i) {
        control.setInkActive(true);
        control.setInkActive(false);
    }
    control.requestCleanup();
    QTimer::singleShot(1000, &wait, &QEventLoop::quit);
    wait.exec();
    if (backend.pushes != pushes || backend.pops != pops || backend.cleanups != 1 || statusChanges != 0) return 11;
    // Switching between sustained Pen and default must balance the owned stack.
    control.setInkActive(true);
    control.setCanvasPenMode(false); // Refuse a policy change during a stroke.
    if (!control.canvasPenMode()) return 15;
    control.setInkActive(false);
    control.setCanvasPenMode(false);
    if (!backend.stack.isEmpty()) return 16;
    const int defaultPushes = backend.pushes, defaultPops = backend.pops;
    for (int i = 0; i < 20; ++i) {
        control.setInkActive(true); control.setInkActive(false);
    }
    if (backend.pushes != defaultPushes || backend.pops != defaultPops) return 17;
    control.setCanvasPenMode(true);
    if (backend.stack != QVector<EPScreenMode>{EPScreenMode::Pen}) return 18;
    control.setCanvasActive(false);
    if (backend.stack != QVector<EPScreenMode>{EPScreenMode::UI}) return 12;
    control.setMotionActive(true);
    if (backend.stack != QVector<EPScreenMode>{EPScreenMode::Animation}) return 13;
    control.setMotionActive(false);
    if (backend.stack != QVector<EPScreenMode>{EPScreenMode::UI}) return 14;
    control.shutdown();
    if (!backend.stack.isEmpty() || control.available()) return 8;
    TestControl unsupported;
    QObject object;
    if (unsupported.attachBackend(&object)) return 9;
    qInfo() << "PASS: Qt control invocation, balanced modes, idle cleanup, sustained/default canvas without per-stroke control calls, scroll-policy restoration and unsupported backend refusal";
    return 0;
}
