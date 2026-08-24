#pragma once

#include <QMainWindow>

#include "transport/protocol_client.h"
#include "accessibility/accessibility_announcer.h"

class QLabel;
class QLineEdit;
class QEvent;

namespace indiginous::world {
class WorldViewport;
}

namespace indiginous::app {

class MainWindow final : public QMainWindow {
    Q_OBJECT

public:
    explicit MainWindow(QWidget* parent = nullptr);

private slots:
    void showSettings();
    void showAbout();
    void connectToEndpoint();
    void updateConnectionStatus(indiginous::transport::ConnectionState state);
    void showStatus(const QString& message);
    void handleAuthenticationRequired(const QString& message);
    void handleAuthenticationResult(bool ok, const QString& message, const QString& sessionToken);
    void handleWelcome(const QJsonObject& welcome);
    void handleLocation(const QString& locationId, const QString& locationName, int x, int y);
    void activateWorld();

private:
    void buildMenus();
    void buildCentralView();
    bool event(QEvent* event) override;

    indiginous::transport::ProtocolClient protocolClient_;
    indiginous::accessibility::AccessibilityAnnouncer accessibilityAnnouncer_;
    indiginous::world::WorldViewport* viewport_ = nullptr;
    QLineEdit* endpointEdit_ = nullptr;
    QLineEdit* usernameEdit_ = nullptr;
    QLineEdit* passwordEdit_ = nullptr;
    QLineEdit* nicknameEdit_ = nullptr;
    QLabel* connectionLabel_ = nullptr;
    QLabel* authLabel_ = nullptr;
};

}  // namespace indiginous::app
