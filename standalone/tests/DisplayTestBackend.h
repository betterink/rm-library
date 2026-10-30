#pragma once
#include "EpaperDisplayControl.h"
#include <QtCore/QVector>

class DisplayTestBackend : public QObject {
    Q_OBJECT
public:
    QVector<EPScreenMode> stack;
    int cleanups = 0;
    int pushes = 0, pops = 0;
public slots:
    void pushGlobalScreenMode(EPScreenMode mode) { ++pushes; stack.append(mode); }
    void popGlobalScreenMode() { ++pops; if (!stack.isEmpty()) stack.removeLast(); }
    void clearGhosting() { ++cleanups; }
};
