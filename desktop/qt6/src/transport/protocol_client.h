#pragma once

#include <QObject>
#include <QJsonObject>
#include <QString>
#include <QAbstractSocket>
#include <QWebSocket>

namespace indiginous::transport {

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
    void login(const QString& username, const QString& password);
    void continueAsGuest(const QString& nickname);
    void resume(const QString& sessionToken);
    void sendMove(int x, int y);
    void changeLocation(const QString& locationId);
    void sendChat(const QString& message);
    void welcomeReady();
    void markAuthenticated();
    void markWelcomeReady();

signals:
    void stateChanged(indiginous::transport::ConnectionState state);
    void statusMessage(const QString& message);
    void authenticationRequired(const QString& message);
    void authenticationResult(bool ok, const QString& message, const QString& sessionToken);
    void welcomeReceived(const QJsonObject& welcome);
    void positionReceived(const QJsonObject& position);
    void locationReceived(const QJsonObject& location);

private:
    void setState(ConnectionState state);
    void sendObject(const QJsonObject& payload);
    void handleTextMessage(const QString& message);
    void handleConnected();
    void handleDisconnected();
    void handleSocketError(QAbstractSocket::SocketError error);

    ConnectionState state_ = ConnectionState::Disconnected;
    QString endpoint_;
    QWebSocket socket_;
};

}  // namespace indiginous::transport
