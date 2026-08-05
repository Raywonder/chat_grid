#pragma once

#include <QMainWindow>

#include "transport/protocol_client.h"

class QLabel;
class QLineEdit;

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

private:
    void buildMenus();
    void buildCentralView();

    indiginous::transport::ProtocolClient protocolClient_;
    indiginous::world::WorldViewport* viewport_ = nullptr;
    QLineEdit* endpointEdit_ = nullptr;
    QLabel* connectionLabel_ = nullptr;
};

}  // namespace indiginous::app
