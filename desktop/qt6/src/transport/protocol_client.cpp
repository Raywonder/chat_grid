#include "transport/protocol_client.h"

#include <QJsonDocument>
#include <QNetworkRequest>

namespace indiginous::transport {

ProtocolClient::ProtocolClient(QObject* parent) : QObject(parent) {
    socket_.setParent(this);
    connect(&socket_, &QWebSocket::connected, this, &ProtocolClient::handleConnected);
    connect(&socket_, &QWebSocket::disconnected, this, &ProtocolClient::handleDisconnected);
    connect(&socket_, &QWebSocket::textMessageReceived, this, &ProtocolClient::handleTextMessage);
    connect(&socket_, &QWebSocket::errorOccurred, this, &ProtocolClient::handleSocketError);
}

ConnectionState ProtocolClient::state() const noexcept {
    return state_;
}

QString ProtocolClient::stateText() const {
    switch (state_) {
    case ConnectionState::Disconnected: return QStringLiteral("Disconnected");
    case ConnectionState::Connecting: return QStringLiteral("Connecting");
    case ConnectionState::AwaitingAuthentication: return QStringLiteral("Awaiting authentication");
    case ConnectionState::Authenticating: return QStringLiteral("Authenticating");
    case ConnectionState::Authenticated: return QStringLiteral("Authenticated");
    case ConnectionState::Ready: return QStringLiteral("World ready");
    case ConnectionState::Reconnecting: return QStringLiteral("Reconnecting");
    }
    return QStringLiteral("Unknown");
}

void ProtocolClient::connectToServer(const QString& endpoint) {
    endpoint_ = endpoint.trimmed();
    if (endpoint_.isEmpty()) {
        emit statusMessage(QStringLiteral("Enter an Indiginous endpoint first."));
        return;
    }
    if (!endpoint_.startsWith(QStringLiteral("wss://"), Qt::CaseInsensitive)
        && !endpoint_.startsWith(QStringLiteral("ws://"), Qt::CaseInsensitive)) {
        emit statusMessage(QStringLiteral("Use a secure Indiginous websocket endpoint beginning with wss://."));
        return;
    }
    socket_.abort();
    setState(ConnectionState::Connecting);
    QNetworkRequest request{QUrl(endpoint_)};
    request.setRawHeader("Origin", "https://blind.software");
    socket_.open(request);
}

void ProtocolClient::disconnectFromServer() {
    socket_.close();
    endpoint_.clear();
    setState(ConnectionState::Disconnected);
    emit statusMessage(QStringLiteral("Disconnected."));
}

void ProtocolClient::login(const QString& username, const QString& password) {
    sendObject(QJsonObject{{"type", "auth_login"}, {"username", username}, {"password", password}});
}

void ProtocolClient::continueAsGuest(const QString& nickname) {
    QJsonObject payload{{"type", "auth_guest"}};
    if (!nickname.trimmed().isEmpty()) payload.insert("nickname", nickname.trimmed());
    sendObject(payload);
}

void ProtocolClient::resume(const QString& sessionToken) {
    sendObject(QJsonObject{{"type", "auth_resume"}, {"sessionToken", sessionToken}});
}

void ProtocolClient::sendMove(int x, int y) {
    sendObject(QJsonObject{{"type", "update_position"}, {"x", x}, {"y", y}});
}

void ProtocolClient::changeLocation(const QString& locationId) {
    sendObject(QJsonObject{{"type", "change_location"}, {"locationId", locationId}});
}

void ProtocolClient::sendChat(const QString& message) {
    if (!message.trimmed().isEmpty()) sendObject(QJsonObject{{"type", "chat_message"}, {"message", message.trimmed()}});
}

void ProtocolClient::welcomeReady() {
    sendObject(QJsonObject{{"type", "welcome_ready"}});
}

void ProtocolClient::markAuthenticated() {
    setState(ConnectionState::Authenticated);
}

void ProtocolClient::markWelcomeReady() {
    setState(ConnectionState::Ready);
}

void ProtocolClient::setState(ConnectionState state) {
    if (state_ == state) {
        return;
    }
    state_ = state;
    emit stateChanged(state_);
}

void ProtocolClient::sendObject(const QJsonObject& payload) {
    if (socket_.state() != QAbstractSocket::ConnectedState) {
        emit statusMessage(QStringLiteral("Indiginous is not connected yet."));
        return;
    }
    socket_.sendTextMessage(QString::fromUtf8(QJsonDocument(payload).toJson(QJsonDocument::Compact)));
}

void ProtocolClient::handleConnected() {
    setState(ConnectionState::AwaitingAuthentication);
    emit statusMessage(QStringLiteral("Connected. Waiting for Indiginous authentication."));
}

void ProtocolClient::handleDisconnected() {
    if (state_ != ConnectionState::Disconnected) setState(ConnectionState::Reconnecting);
    emit statusMessage(QStringLiteral("Indiginous connection closed."));
}

void ProtocolClient::handleSocketError(QAbstractSocket::SocketError error) {
    Q_UNUSED(error)
    emit statusMessage(socket_.errorString());
    setState(ConnectionState::Disconnected);
}

void ProtocolClient::handleTextMessage(const QString& message) {
    const QJsonDocument document = QJsonDocument::fromJson(message.toUtf8());
    if (!document.isObject()) return;
    const QJsonObject object = document.object();
    const QString type = object.value("type").toString();
    if (type == QStringLiteral("auth_required")) {
        setState(ConnectionState::AwaitingAuthentication);
        emit authenticationRequired(object.value("message").toString());
    } else if (type == QStringLiteral("auth_result")) {
        const bool ok = object.value("ok").toBool();
        if (ok) setState(ConnectionState::Authenticated);
        emit authenticationResult(ok, object.value("message").toString(), object.value("sessionToken").toString());
    } else if (type == QStringLiteral("welcome")) {
        setState(ConnectionState::Ready);
        emit welcomeReceived(object);
        welcomeReady();
    } else if (type == QStringLiteral("update_position")) {
        emit positionReceived(object.value("x").toInt(), object.value("y").toInt());
    } else if (type == QStringLiteral("location_changed")) {
        emit locationReceived(object.value("locationId").toString(), object.value("locationName").toString(),
                              object.value("x").toInt(), object.value("y").toInt());
    } else if (type == QStringLiteral("chat_message")) {
        emit statusMessage(QStringLiteral("%1: %2").arg(object.value("senderNickname").toString(), object.value("message").toString()));
    }
}

}  // namespace indiginous::transport
