#include "TabletNavigation.h"
#include <QtGui/QTabletEvent>
#include <QtGui/QMouseEvent>
#include <QtCore/QCoreApplication>

TabletNavigation::TabletNavigation(QQuickWindow *window, QQuickItem *canvas)
    : m_window(window), m_canvas(canvas) {
    if (window) window->installEventFilter(this);
}
bool TabletNavigation::eventFilter(QObject *watched, QEvent *event) {
    if (watched != m_window || !m_window) return false;
    const auto type = event->type();
    if (type != QEvent::TabletPress && type != QEvent::TabletMove && type != QEvent::TabletRelease)
        return false;
    auto *tablet = static_cast<QTabletEvent *>(event);
    if (type == QEvent::TabletPress) {
        // The native canvas already consumes its tablet events. Never duplicate them.
        if (m_canvas && m_canvas->isVisible() && m_canvas->isEnabled()
            && m_canvas->contains(m_canvas->mapFromScene(tablet->position()))) {
            m_navigating = false;
            return false;
        }
        m_navigating = true;
    }
    if (!m_navigating) return false;
    const auto mouseType = type == QEvent::TabletPress ? QEvent::MouseButtonPress
        : type == QEvent::TabletRelease ? QEvent::MouseButtonRelease : QEvent::MouseMove;
    const auto button = type == QEvent::TabletMove ? Qt::NoButton : Qt::LeftButton;
    const Qt::MouseButtons buttons = type == QEvent::TabletRelease ? Qt::NoButton : Qt::LeftButton;
    QMouseEvent mouse(mouseType, tablet->position(), tablet->globalPosition(),
                      button, buttons, tablet->modifiers());
    mouse.setTimestamp(tablet->timestamp());
    QCoreApplication::sendEvent(m_window, &mouse);
    if (type == QEvent::TabletRelease) m_navigating = false;
    tablet->accept();
    return true;
}
