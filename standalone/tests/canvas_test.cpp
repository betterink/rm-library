#include "StrokeSurface.h"
#include <QtGui/QGuiApplication>
#include <QtGui/QMouseEvent>
#include <QtGui/QPainter>
#include <QtCore/QDebug>
#include <QtCore/QEventLoop>
#include <QtCore/QTimer>

class TestSurface : public StrokeSurface {
public:
    using StrokeSurface::mousePressEvent;
    using StrokeSurface::mouseMoveEvent;
    using StrokeSurface::mouseReleaseEvent;
};
int main(int argc, char **argv) {
    QGuiApplication app(argc, argv);
    TestSurface surface; surface.setWidth(200); surface.setHeight(200);
    surface.setFingerEnabled(true);
    QMouseEvent press(QEvent::MouseButtonPress, QPointF(20, 20), QPointF(20, 20),
                      Qt::LeftButton, Qt::LeftButton, Qt::NoModifier);
    QMouseEvent move(QEvent::MouseMove, QPointF(100, 100), QPointF(100, 100),
                     Qt::NoButton, Qt::LeftButton, Qt::NoModifier);
    QMouseEvent release(QEvent::MouseButtonRelease, QPointF(100, 100), QPointF(100, 100),
                        Qt::LeftButton, Qt::NoButton, Qt::NoModifier);
    surface.mousePressEvent(&press); surface.mouseMoveEvent(&move); surface.mouseReleaseEvent(&release);
    QImage result(200, 200, QImage::Format_RGB32); result.fill(Qt::red);
    { QPainter painter(&result); surface.paint(&painter); }
    if (surface.strokeCount() != 1 || result.pixelColor(50, 50) != QColor(Qt::black)
        || result.pixelColor(150, 20) != QColor(Qt::white)) return 1;
    // A partial paint must not erase pixels outside the damaged stroke region.
    QImage partial(200, 200, QImage::Format_RGB32); partial.fill(Qt::red);
    { QPainter painter(&partial); painter.setClipRect(QRect(40, 40, 20, 20)); surface.paint(&painter); }
    if (partial.pixelColor(50, 50) != QColor(Qt::black)
        || partial.pixelColor(150, 20) != QColor(Qt::red)) return 3;
    QEventLoop wait;
    QTimer::singleShot(400, &wait, &QEventLoop::quit);
    wait.exec();
    if (!surface.timingSummary().contains("2 samples")
        || !surface.timingSummary().contains("1 paints")) return 4;
    surface.clear();
    { QPainter painter(&result); surface.paint(&painter); }
    if (surface.strokeCount() != 0 || result.pixelColor(50, 50) != QColor(Qt::white)) return 2;
    qInfo() << "PASS: native stroke rasterization, untouched background and clear";
    return 0;
}
