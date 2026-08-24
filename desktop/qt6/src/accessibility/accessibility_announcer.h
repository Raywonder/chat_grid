#pragma once

#include <QObject>
#include <QString>

class QWidget;

namespace indiginous::accessibility {

class AccessibilityAnnouncer final : public QObject {
    Q_OBJECT

public:
    explicit AccessibilityAnnouncer(QObject* parent = nullptr);

    void announce(QWidget* anchor, const QString& text, bool directSpeech = false, bool interrupt = false);

private:
    bool speakDirectly(const QString& text, bool interrupt);
    void loadNativeSpeechBridge();

    void* nvdaLibrary_ = nullptr;
    unsigned long (*nvdaTestIfRunning_)() = nullptr;
    unsigned long (*nvdaSpeakText_)(const wchar_t*) = nullptr;
    unsigned long (*nvdaCancelSpeech_)() = nullptr;
};

}  // namespace indiginous::accessibility
