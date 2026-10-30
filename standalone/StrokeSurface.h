#pragma once
#include <QtQuick/QQuickPaintedItem>
#include <QtGui/QImage>
#include <QtCore/QPointF>
#include <QtCore/QTimer>
#include <atomic>

// Incremental native raster diagnostic. No Kotlin/IPC in the input/render path.
class StrokeSurface : public QQuickPaintedItem {
    Q_OBJECT
    Q_PROPERTY(QString timingSummary READ timingSummary NOTIFY timingSummaryChanged)
    Q_PROPERTY(bool fingerEnabled READ fingerEnabled WRITE setFingerEnabled NOTIFY fingerEnabledChanged)
    Q_PROPERTY(int tabletEvents READ tabletEvents NOTIFY inputSummaryChanged)
    Q_PROPERTY(int strokeCount READ strokeCount NOTIFY inputSummaryChanged)
    Q_PROPERTY(bool drawingActive READ drawingActive NOTIFY drawingActiveChanged)
public:
    explicit StrokeSurface(QQuickItem *parent = nullptr);
    QString timingSummary() const { return m_timingSummary; }
    bool fingerEnabled() const { return m_fingerEnabled; }
    void setFingerEnabled(bool enabled);
    int tabletEvents() const { return m_tabletEvents; }
    int strokeCount() const { return m_strokeCount; }
    bool drawingActive() const { return m_active; }
    Q_INVOKABLE void clear();
    void paint(QPainter *) override;
signals:
    void timingSummaryChanged();
    void fingerEnabledChanged();
    void inputSummaryChanged();
    void drawingActiveChanged();
protected:
    bool eventFilter(QObject *, QEvent *) override;
    void mousePressEvent(QMouseEvent *) override;
    void mouseMoveEvent(QMouseEvent *) override;
    void mouseReleaseEvent(QMouseEvent *) override;
    void geometryChange(const QRectF &, const QRectF &) override;
private:
    // Atomic because paint() may execute on Qt's render thread. No per-point logging.
    std::atomic<qint64> m_pendingSince{0}, m_waitTotal{0}, m_waitMax{0};
    std::atomic<int> m_paints{0};
    QTimer m_report;
    QString m_timingSummary = "Draw, then pause to collect paint timing.";
    qint64 m_rasterNs = 0;
    int m_samples = 0;
    void reportTiming();
    QImage m_image;
    QPointF m_lastPoint;
    float m_lastWidth = 2;
    int m_strokeCount = 0;
    bool m_active = false;
    bool m_tabletActive = false;
    bool m_fingerEnabled = false;
    int m_tabletEvents = 0;
    void begin(const QPointF &, float);
    void append(const QPointF &, float);
    void finish();
};
