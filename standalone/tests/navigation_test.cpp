#include "TabletNavigation.h"
#include "StrokeSurface.h"
#include <QtGui/QGuiApplication>
#include <QtGui/QPointingDevice>
#include <QtGui/QTabletEvent>
#include <QtGui/QMouseEvent>
#include <QtCore/QDebug>

class TestWindow : public QQuickWindow {
public:
    int presses = 0, moves = 0, releases = 0;
    bool event(QEvent *event) override {
        if (event->type() == QEvent::MouseButtonPress) { ++presses; return true; }
        if (event->type() == QEvent::MouseMove) { ++moves; return true; }
        if (event->type() == QEvent::MouseButtonRelease) { ++releases; return true; }
        return QQuickWindow::event(event);
    }
};
int main(int argc, char **argv) {
    QGuiApplication app(argc, argv);
    TestWindow window; window.resize(200, 200); window.show();
    StrokeSurface canvas(window.contentItem());
    canvas.setX(50); canvas.setY(50); canvas.setWidth(100); canvas.setHeight(100);
    TabletNavigation navigation(&window, &canvas);
    QPointingDevice pen("test pen", 123, QInputDevice::DeviceType::Stylus,
        QPointingDevice::PointerType::Pen,
        QInputDevice::Capability::Position | QInputDevice::Capability::Pressure, 1, 1);
    const auto send = [&](QEvent::Type type, QPointF position) {
        const auto button = type == QEvent::TabletMove ? Qt::NoButton : Qt::LeftButton;
        const Qt::MouseButtons buttons = type == QEvent::TabletRelease ? Qt::NoButton : Qt::LeftButton;
        QTabletEvent event(type, &pen, position, position, 0.5, 0, 0, 0, 0, 0,
                           Qt::NoModifier, button, buttons);
        QCoreApplication::sendEvent(&window, &event);
    };
    send(QEvent::TabletPress, {10, 10});
    send(QEvent::TabletMove, {70, 70}); // Moving into the canvas must keep the pointer grab.
    send(QEvent::TabletRelease, {70, 70});
    if (window.presses != 1 || window.moves != 1 || window.releases != 1 || canvas.strokeCount() != 0) return 1;
    send(QEvent::TabletPress, {60, 60});
    send(QEvent::TabletMove, {90, 90});
    send(QEvent::TabletRelease, {10, 10}); // Leaving the canvas must finish the original stroke.
    if (window.presses != 1 || window.releases != 1 || canvas.strokeCount() != 1 || canvas.tabletEvents() != 3) {
        qWarning() << "Canvas isolation failed:" << window.presses << window.releases
                   << canvas.strokeCount() << canvas.tabletEvents() << canvas.window() << &window;
        return 2;
    }
    qInfo() << "PASS: pen navigation press/move/release and native-canvas isolation";
    return 0;
}
