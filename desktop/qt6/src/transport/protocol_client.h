#pragma once

#include <QObject>
#include <QString>

namespace chatgrid::transport {

enum class ConnectionState {
    Disconnected,
    Connecting,
    AwaitingAuthentication,
    Authenticating,
    Authenticated,
    Ready,
    Reconnecting,
};

enum class ClientPacket {
    AuthRegister,
    AuthLogin,
    AuthResume,
    AuthLogout,
    WelcomeReady,
    ChangeLocation,
    UpdatePosition,
    ChatMessage,
    DirectMessage,
    ItemUse,
    ItemUpdate,
    Ping,
};

class ProtocolClient final : public QObject {
    Q_OBJECT

public:
    explicit ProtocolClient(QObject* parent = nullptr);

    ConnectionState state() const noexcept;
    QString stateText() const;

public slots:
    void connectToServer(const QString& endpoint);
    void disconnectFromServer();
    void markAuthenticated();
    void markWelcomeReady();

signals:
    void stateChanged(chatgrid::transport::ConnectionState state);
    void statusMessage(const QString& message);

private:
    void setState(ConnectionState state);

    ConnectionState state_ = ConnectionState::Disconnected;
    QString endpoint_;
};

}  // namespace chatgrid::transport
