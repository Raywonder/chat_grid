#include "app/main_window.h"

#include <QAction>
#include <QDialog>
#include <QDialogButtonBox>
#include <QEvent>
#include <QFormLayout>
#include <QGroupBox>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QMenuBar>
#include <QPushButton>
#include <QStatusBar>
#include <QTextEdit>
#include <QVBoxLayout>
#include <QJsonObject>

#include "world/world_viewport.h"

namespace indiginous::app {

MainWindow::MainWindow(QWidget* parent) : QMainWindow(parent) {
    setWindowTitle(QStringLiteral("Indiginous — Native Qt 6"));
    resize(900, 620);
    buildMenus();
    buildCentralView();

    connect(&protocolClient_, &transport::ProtocolClient::stateChanged,
            this, &MainWindow::updateConnectionStatus);
    connect(&protocolClient_, &transport::ProtocolClient::statusMessage,
            this, &MainWindow::showStatus);
    connect(&protocolClient_, &transport::ProtocolClient::authenticationRequired,
            this, &MainWindow::handleAuthenticationRequired);
    connect(&protocolClient_, &transport::ProtocolClient::authenticationResult,
            this, &MainWindow::handleAuthenticationResult);
    connect(&protocolClient_, &transport::ProtocolClient::welcomeReceived,
            this, &MainWindow::handleWelcome);
    connect(&protocolClient_, &transport::ProtocolClient::locationReceived,
            this, &MainWindow::handleLocation);
    connect(viewport_, &world::WorldViewport::viewportStatus,
            this, &MainWindow::showStatus);
    connect(viewport_, &world::WorldViewport::moveRequested,
            &protocolClient_, &transport::ProtocolClient::sendMove);
    updateConnectionStatus(protocolClient_.state());
}

void MainWindow::buildMenus() {
    auto* fileMenu = menuBar()->addMenu(QStringLiteral("&Indiginous"));
    auto* connectAction = fileMenu->addAction(QStringLiteral("&Connect"));
    connectAction->setShortcut(QKeySequence(QStringLiteral("Ctrl+L")));
    connect(connectAction, &QAction::triggered, this, &MainWindow::connectToEndpoint);
    auto* disconnectAction = fileMenu->addAction(QStringLiteral("&Disconnect"));
    connect(disconnectAction, &QAction::triggered, &protocolClient_, &transport::ProtocolClient::disconnectFromServer);
    fileMenu->addSeparator();
    auto* quitAction = fileMenu->addAction(QStringLiteral("E&xit"));
    quitAction->setShortcut(QKeySequence::Quit);
    connect(quitAction, &QAction::triggered, this, &QWidget::close);

    auto* viewMenu = menuBar()->addMenu(QStringLiteral("&View"));
    auto* settingsAction = viewMenu->addAction(QStringLiteral("&Settings…"));
    connect(settingsAction, &QAction::triggered, this, &MainWindow::showSettings);

    auto* helpMenu = menuBar()->addMenu(QStringLiteral("&Help"));
    auto* aboutAction = helpMenu->addAction(QStringLiteral("&About Indiginous Native Qt 6"));
    connect(aboutAction, &QAction::triggered, this, &MainWindow::showAbout);
}

void MainWindow::buildCentralView() {
    auto* root = new QWidget(this);
    auto* layout = new QVBoxLayout(root);
    auto* connectionBox = new QGroupBox(QStringLiteral("Connection"), root);
    auto* connectionLayout = new QHBoxLayout(connectionBox);
    endpointEdit_ = new QLineEdit(QStringLiteral("wss://blind.software/indiginous/ws"), connectionBox);
    endpointEdit_->setAccessibleName(QStringLiteral("Indiginous server endpoint"));
    auto* connectButton = new QPushButton(QStringLiteral("Connect"), connectionBox);
    connectButton->setDefault(true);
    connect(connectButton, &QPushButton::clicked, this, &MainWindow::connectToEndpoint);
    connectionLabel_ = new QLabel(connectionBox);
    connectionLayout->addWidget(endpointEdit_, 1);
    connectionLayout->addWidget(connectButton);
    connectionLayout->addWidget(connectionLabel_);
    layout->addWidget(connectionBox);

    auto* authBox = new QGroupBox(QStringLiteral("Sign in"), root);
    auto* authLayout = new QFormLayout(authBox);
    usernameEdit_ = new QLineEdit(authBox);
    usernameEdit_->setAccessibleName(QStringLiteral("Indiginous username"));
    passwordEdit_ = new QLineEdit(authBox);
    passwordEdit_->setEchoMode(QLineEdit::Password);
    passwordEdit_->setAccessibleName(QStringLiteral("Indiginous password"));
    nicknameEdit_ = new QLineEdit(QStringLiteral("Guest"), authBox);
    nicknameEdit_->setAccessibleName(QStringLiteral("Guest nickname"));
    auto* loginButton = new QPushButton(QStringLiteral("Sign in"), authBox);
    auto* guestButton = new QPushButton(QStringLiteral("Continue as guest"), authBox);
    authLabel_ = new QLabel(QStringLiteral("Connect first, then sign in or continue as guest."), authBox);
    authLayout->addRow(QStringLiteral("Username:"), usernameEdit_);
    authLayout->addRow(QStringLiteral("Password:"), passwordEdit_);
    authLayout->addRow(loginButton, guestButton);
    authLayout->addRow(authLabel_);
    authLayout->addRow(QStringLiteral("Guest name:"), nicknameEdit_);
    connect(loginButton, &QPushButton::clicked, this, [this] {
        protocolClient_.login(usernameEdit_->text(), passwordEdit_->text());
    });
    connect(guestButton, &QPushButton::clicked, this, [this] {
        protocolClient_.continueAsGuest(nicknameEdit_->text());
    });
    layout->addWidget(authBox);

    viewport_ = new world::WorldViewport(root);
    layout->addWidget(viewport_, 1);
    setCentralWidget(root);
    statusBar()->showMessage(QStringLiteral("Native Indiginous client — no server connection yet."));
    viewport_->setFocus();
}

void MainWindow::connectToEndpoint() {
    protocolClient_.connectToServer(endpointEdit_->text());
}

void MainWindow::updateConnectionStatus(transport::ConnectionState state) {
    Q_UNUSED(state)
    connectionLabel_->setText(protocolClient_.stateText());
}

void MainWindow::showStatus(const QString& message) {
    statusBar()->showMessage(message);
    accessibilityAnnouncer_.announce(statusBar(), message);
}

void MainWindow::handleAuthenticationRequired(const QString& message) {
    authLabel_->setText(message.isEmpty() ? QStringLiteral("Sign in or continue as guest.") : message);
    usernameEdit_->setFocus();
}

void MainWindow::handleAuthenticationResult(bool ok, const QString& message, const QString& sessionToken) {
    Q_UNUSED(sessionToken)
    authLabel_->setText(message);
    if (ok) activateWorld();
}

void MainWindow::handleWelcome(const QJsonObject& welcome) {
    viewport_->applyWelcome(welcome);
    activateWorld();
    showStatus(QStringLiteral("World connected."));
    accessibilityAnnouncer_.announce(
        statusBar(),
        QStringLiteral("World joined. Location: %1. Arrow keys or W A S D move.")
            .arg(viewport_->snapshot().locationName),
        true,
        true);
}

void MainWindow::handleLocation(const QString& locationId, const QString& locationName, int x, int y) {
    auto snapshot = viewport_->snapshot();
    snapshot.locationId = locationId;
    snapshot.locationName = locationName;
    snapshot.playerPosition = QPointF(x, y);
    viewport_->applySnapshot(snapshot);
    activateWorld();
}

void MainWindow::activateWorld() {
    if (isMinimized()) return;
    viewport_->setFocus(Qt::OtherFocusReason);
}

bool MainWindow::event(QEvent* event) {
    if (event->type() == QEvent::WindowActivate || event->type() == QEvent::Show) {
        QMetaObject::invokeMethod(this, &MainWindow::activateWorld, Qt::QueuedConnection);
    }
    return QMainWindow::event(event);
}

void MainWindow::showSettings() {
    QDialog dialog(this);
    dialog.setWindowTitle(QStringLiteral("Indiginous Settings"));
    auto* layout = new QVBoxLayout(&dialog);
    auto* form = new QFormLayout;
    form->addRow(QStringLiteral("Server endpoint:"), new QLineEdit(endpointEdit_->text(), &dialog));
    form->addRow(QStringLiteral("Audio devices:"), new QLabel(QStringLiteral("Native audio device enumeration is not ported yet."), &dialog));
    form->addRow(QStringLiteral("Accessibility:"), new QLabel(QStringLiteral("Qt accessibility hooks will be completed with the native controls."), &dialog));
    layout->addLayout(form);
    auto* buttons = new QDialogButtonBox(QDialogButtonBox::Close, &dialog);
    connect(buttons, &QDialogButtonBox::rejected, &dialog, &QDialog::reject);
    layout->addWidget(buttons);
    dialog.exec();
}

void MainWindow::showAbout() {
    QDialog dialog(this);
    dialog.setWindowTitle(QStringLiteral("About Indiginous Native Qt 6"));
    auto* layout = new QVBoxLayout(&dialog);
    auto* text = new QTextEdit(&dialog);
    text->setReadOnly(true);
    text->setPlainText(QStringLiteral(
        "Indiginous native Qt 6 client\n\n"
        "Native menus, secure websocket transport, authentication, guest entry, "
        "world snapshots, keyboard movement, and automatic world focus are active.\n\n"
        "Media, spatial audio, WebRTC voice, and platform packaging remain in the next porting phase."));
    layout->addWidget(text);
    auto* buttons = new QDialogButtonBox(QDialogButtonBox::Close, &dialog);
    connect(buttons, &QDialogButtonBox::rejected, &dialog, &QDialog::reject);
    layout->addWidget(buttons);
    dialog.exec();
}

}  // namespace indiginous::app
