#include "StrokeSurface.h"
#include <QtQuick/QQuickWindow>
#include <QtGui/QTabletEvent>
#include <QtGui/QMouseEvent>
#include <QtGui/QPainter>
#include <QtGui/QPen>
#include <cmath>
#include <chrono>
#include <QtCore/QDebug>

static qint64 clockNs() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}

StrokeSurface::StrokeSurface(QQuickItem *parent) : QQuickPaintedItem(parent) {
    m_report.setSingleShot(true);
    m_report.setInterval(300);
    connect(&m_report, &QTimer::timeout, this, &StrokeSurface::reportTiming);
    setClip(true);
    setOpaquePainting(true);
    setAntialiasing(false);
    setAcceptedMouseButtons(Qt::NoButton);
    connect(this, &QQuickItem::windowChanged, this, [this](QQuickWindow *window) {
        if (window) window->installEventFilter(this);
    });
    // A C++ caller may supply a parent already attached to a window, so the
    // initial windowChanged signal can have occurred before this constructor.
    if (window()) window()->installEventFilter(this);
}
void StrokeSurface::setFingerEnabled(bool enabled) {
    if (m_fingerEnabled == enabled) return;
    m_fingerEnabled = enabled;
    setAcceptedMouseButtons(enabled ? Qt::LeftButton : Qt::NoButton);
    emit fingerEnabledChanged();
}
void StrokeSurface::geometryChange(const QRectF &next, const QRectF &old) {
    QQuickPaintedItem::geometryChange(next, old);
    const QSize size(qMax(1, int(std::ceil(next.width()))), qMax(1, int(std::ceil(next.height()))));
    if (size == m_image.size()) return;
    QImage resized(size, QImage::Format_RGB32); resized.fill(Qt::white);
    if (!m_image.isNull()) { QPainter painter(&resized); painter.drawImage(0, 0, m_image); }
    m_image = resized; update();
}
void StrokeSurface::paint(QPainter *painter) {
    const qint64 pending = m_pendingSince.exchange(0);
    if (pending) {
        const qint64 wait = clockNs() - pending;
        m_waitTotal.fetch_add(wait);
        qint64 previous = m_waitMax.load();
        while (previous < wait && !m_waitMax.compare_exchange_weak(previous, wait)) {}
        m_paints.fetch_add(1);
    }
    // Respect the paint engine's clip; only copy the requested region.
    if (painter->hasClipping()) {
        const QRectF area = painter->clipBoundingRect().intersected(m_image.rect());
        painter->drawImage(area, m_image, area);
    } else painter->drawImage(QPointF(0, 0), m_image);
}
void StrokeSurface::reportTiming() {
    const int paints = m_paints.load();
    m_timingSummary = QString("%1 samples · %2 paints · raster %3 ms/sample · paint wait avg %4 / max %5 ms")
        .arg(m_samples).arg(paints)
        .arg(m_samples ? double(m_rasterNs) / m_samples / 1e6 : 0, 0, 'f', 3)
        .arg(paints ? double(m_waitTotal.load()) / paints / 1e6 : 0, 0, 'f', 2)
        .arg(double(m_waitMax.load()) / 1e6, 0, 'f', 2);
    qInfo().noquote() << "Ink timing (event handler to paint, NOT physical display latency):" << m_timingSummary;
    emit timingSummaryChanged();
}
void StrokeSurface::clear() {
    if (!m_image.isNull()) m_image.fill(Qt::white);
    m_strokeCount = 0; m_tabletActive = false;
    finish();
    update(); emit inputSummaryChanged();
}
void StrokeSurface::begin(const QPointF &point, float pressure) {
    if (m_image.isNull()) return;
    // Accumulate a writing burst, report only after a pause. Avoid UI churn
    // between closely spaced strokes, and avoid resetting render-thread counters.
    if (!m_report.isActive()) {
        m_samples = 0; m_rasterNs = 0;
        m_waitTotal.store(0); m_waitMax.store(0); m_paints.store(0);
    }
    m_report.stop();
    m_active = true; ++m_strokeCount;
    emit drawingActiveChanged();
    m_lastPoint = point; m_lastWidth = 2.0f + qBound(0.0f, pressure, 1.0f) * 5.0f;
    append(point, pressure);
}
void StrokeSurface::append(const QPointF &point, float pressure) {
    if (!m_active || m_image.isNull()) return;
    const qint64 started = clockNs();
    const QPointF bounded(qBound(0.0, point.x(), width()), qBound(0.0, point.y(), height()));
    const float penWidth = 2.0f + qBound(0.0f, pressure, 1.0f) * 5.0f;
    {
        QPainter painter(&m_image);
        painter.setPen(QPen(Qt::black, (penWidth + m_lastWidth) / 2, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin));
        if (bounded == m_lastPoint) painter.drawPoint(bounded);
        else painter.drawLine(m_lastPoint, bounded);
    }
    const qreal margin = qMax(penWidth, m_lastWidth) / 2 + 2;
    const QRect dirty = QRectF(m_lastPoint, bounded).normalized()
        .adjusted(-margin, -margin, margin, margin).toAlignedRect();
    m_lastPoint = bounded; m_lastWidth = penWidth;
    ++m_samples;
    m_rasterNs += clockNs() - started;
    qint64 empty = 0;
    m_pendingSince.compare_exchange_strong(empty, started);
    update(dirty); // Request changed stroke regions, not a full canvas repaint.
}
void StrokeSurface::finish() {
    const bool wasActive = m_active;
    m_active = false;
    if (wasActive) { emit drawingActiveChanged(); m_report.start(); }
    emit inputSummaryChanged();
}
bool StrokeSurface::eventFilter(QObject *watched, QEvent *event) {
    if (watched != window() || !isVisible() || !isEnabled()) return false;
    const auto type = event->type();
    if (type != QEvent::TabletPress && type != QEvent::TabletMove && type != QEvent::TabletRelease)
        return false;
    auto *tablet = static_cast<QTabletEvent *>(event);
    const QPointF point = mapFromScene(tablet->position());
    if (type == QEvent::TabletPress) {
        if (!contains(point)) return false;
        m_tabletActive = true; ++m_tabletEvents; begin(point, float(tablet->pressure()));
    } else {
        if (!m_tabletActive) return false;
        ++m_tabletEvents; append(point, float(tablet->pressure()));
        if (type == QEvent::TabletRelease) { m_tabletActive = false; finish(); }
    }
    tablet->accept(); return true;
}
void StrokeSurface::mousePressEvent(QMouseEvent *event) {
    if (!m_fingerEnabled || m_tabletActive) { event->ignore(); return; }
    begin(event->position(), 0.5f); event->accept();
}
void StrokeSurface::mouseMoveEvent(QMouseEvent *event) {
    if (m_fingerEnabled && !m_tabletActive && m_active) append(event->position(), 0.5f);
    event->accept();
}
void StrokeSurface::mouseReleaseEvent(QMouseEvent *event) {
    if (m_fingerEnabled && !m_tabletActive) finish();
    event->accept();
}
