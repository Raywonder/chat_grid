#include "accessibility/accessibility_announcer.h"

#include <QAccessible>
#include <QAccessibleEvent>
#include <QCoreApplication>
#include <QLibrary>
#include <QProcess>
#include <QWidget>

#ifdef Q_OS_WIN
#include <windows.h>
#endif

namespace indiginous::accessibility {

namespace {
constexpr int kMaximumAnnouncementLength = 2000;
}

AccessibilityAnnouncer::AccessibilityAnnouncer(QObject* parent) : QObject(parent) {
    loadNativeSpeechBridge();
}

void AccessibilityAnnouncer::announce(QWidget* anchor, const QString& text, bool directSpeech, bool interrupt) {
    if (!anchor) return;
    const QString clean = text.simplified().left(kMaximumAnnouncementLength);
    if (clean.isEmpty()) return;

    // This is the cross-screen-reader path: NVDA, Narrator, JAWS, VoiceOver,
    // and other ATs can observe the same accessible-name change.
    anchor->setAccessibleName(clean);
    QAccessibleEvent event(anchor, QAccessible::NameChanged);
    QAccessible::updateAccessibility(&event);

    // Keep a direct NVDA route for world-critical announcements where a
    // status-name change may be delayed behind a busy native control tree.
    if (directSpeech) speakDirectly(clean, interrupt);
}

void AccessibilityAnnouncer::loadNativeSpeechBridge() {
#ifdef Q_OS_WIN
    auto* library = new QLibrary(QCoreApplication::applicationDirPath() + "/nvda/nvdaControllerClient.dll", this);
    if (!library->load()) {
        delete library;
        return;
    }
    nvdaLibrary_ = library;
    nvdaTestIfRunning_ = reinterpret_cast<unsigned long (*)()>(library->resolve("nvdaController_testIfRunning"));
    nvdaSpeakText_ = reinterpret_cast<unsigned long (*)(const wchar_t*)>(library->resolve("nvdaController_speakText"));
    nvdaCancelSpeech_ = reinterpret_cast<unsigned long (*)()>(library->resolve("nvdaController_cancelSpeech"));
    if (!nvdaTestIfRunning_ || !nvdaSpeakText_ || !nvdaCancelSpeech_) {
        library->unload();
        delete library;
        nvdaLibrary_ = nullptr;
    }
#endif
}

bool AccessibilityAnnouncer::speakDirectly(const QString& text, bool interrupt) {
#ifdef Q_OS_WIN
    if (nvdaLibrary_ && nvdaTestIfRunning_() == 0) {
        if (interrupt) nvdaCancelSpeech_();
        return nvdaSpeakText_(reinterpret_cast<const wchar_t*>(text.utf16())) == 0;
    }
#elif defined(Q_OS_MACOS)
    if (interrupt) QProcess::execute(QStringLiteral("killall"), {QStringLiteral("say")});
    return QProcess::startDetached(QStringLiteral("say"), {text});
#else
    Q_UNUSED(text)
    Q_UNUSED(interrupt)
#endif
    return false;
}

}  // namespace indiginous::accessibility
