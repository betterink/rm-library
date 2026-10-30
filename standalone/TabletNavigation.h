#pragma once
#include <QtCore/QObject>
#include <QtCore/QPointer>
#include <QtQuick/QQuickItem>
#include <QtQuick/QQuickWindow>

// Route pen contacts outside the drawing surface through Qt Quick's mouse path.
// A contact stays with its initial destination until release.
class TabletNavigation : public QObject {
public:
    TabletNavigation(QQuickWindow *window, QQuickItem *canvas);
protected:
    bool eventFilter(QObject *, QEvent *) override;
private:
    QPointer<QQuickWindow> m_window;
    QPointer<QQuickItem> m_canvas;
    bool m_navigating = false;
};
