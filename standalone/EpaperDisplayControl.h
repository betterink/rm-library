#pragma once
#include <QtCore/QObject>
#include <QtCore/QPointer>
#include <QtCore/QLibrary>
#include <QtCore/QTimer>

// Values verified in the captured 3.29 library's Qt Mode enum, not raw waveforms.
enum class EPScreenMode : int { Pen = 0, Mono = 1, Animation = 2, UI = 3, Content = 4, Sleep = 5, Overlay = 6 };
Q_DECLARE_METATYPE(EPScreenMode)

class EpaperDisplayControl : public QObject {
    Q_OBJECT
    Q_PROPERTY(bool available READ available NOTIFY changed)
    Q_PROPERTY(bool enabled READ enabled WRITE setEnabled NOTIFY changed)
    Q_PROPERTY(bool canvasPenMode READ canvasPenMode WRITE setCanvasPenMode NOTIFY changed)
    Q_PROPERTY(QString status READ status NOTIFY changed)
public:
    explicit EpaperDisplayControl(QObject *parent = nullptr);
    bool available() const { return !m_backend.isNull(); }
    bool enabled() const { return m_enabled; }
    bool canvasPenMode() const { return m_canvasPenMode; }
    QString status() const { return m_status; }
    void initialize();
    void shutdown();
    Q_INVOKABLE void setEnabled(bool enabled);
    Q_INVOKABLE void setMotionActive(bool active);
    Q_INVOKABLE void setInkActive(bool active);
    Q_INVOKABLE void setCanvasPenMode(bool enabled);
    Q_INVOKABLE void setCanvasActive(bool active);
    Q_INVOKABLE void requestCleanup();
    Q_INVOKABLE void cleanNow();
signals:
    void changed();
protected:
    bool attachBackend(QObject *backend);
private:
    QPointer<QObject> m_backend;
    QLibrary m_library;
    QTimer m_cleanup;
    QString m_status = "Display controls: waiting for first frame";
    bool m_attempted = false;
    bool m_enabled = true;
    bool m_motion = false;
    bool m_ink = false;
    bool m_canvas = false;
    bool m_canvasPenMode = true;
    bool m_pushed = false;
    EPScreenMode m_mode = EPScreenMode::UI;
    bool popMode();
    void applyMode();
    void fail(const QString &message);
};
