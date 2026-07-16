#pragma once

#include <QMainWindow>

#include "transport/protocol_client.h"

class QLabel;
class QLineEdit;

namespace chatgrid::world {
class WorldViewport;
}

namespace chatgrid::app {

class MainWindow final : public QMainWindow {
    Q_OBJECT

public:
    explicit MainWindow(QWidget* parent = nullptr);

private slots:
    void showSettings();
    void showAbout();
    void connectToEndpoint();
    void updateConnectionStatus(chatgrid::transport::ConnectionState state);
    void showStatus(const QString& message);

private:
    void buildMenus();
    void buildCentralView();

    chatgrid::transport::ProtocolClient protocolClient_;
    chatgrid::world::WorldViewport* viewport_ = nullptr;
    QLineEdit* endpointEdit_ = nullptr;
    QLabel* connectionLabel_ = nullptr;
};

}  // namespace chatgrid::app
