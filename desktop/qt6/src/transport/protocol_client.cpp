#include "transport/protocol_client.h"

namespace chatgrid::transport {

ProtocolClient::ProtocolClient(QObject* parent) : QObject(parent) {}

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
        emit statusMessage(QStringLiteral("Enter an Endiginous endpoint first."));
        return;
    }
    setState(ConnectionState::Connecting);
    emit statusMessage(QStringLiteral("Transport seam ready for %1; network protocol is not ported yet.").arg(endpoint_));
    setState(ConnectionState::AwaitingAuthentication);
}

void ProtocolClient::disconnectFromServer() {
    endpoint_.clear();
    setState(ConnectionState::Disconnected);
    emit statusMessage(QStringLiteral("Disconnected."));
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

}  // namespace chatgrid::transport
