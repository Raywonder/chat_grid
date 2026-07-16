#include "app/main_window.h"

#include <QAction>
#include <QDialog>
#include <QDialogButtonBox>
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

#include "world/world_viewport.h"

namespace chatgrid::app {

MainWindow::MainWindow(QWidget* parent) : QMainWindow(parent) {
    setWindowTitle(QStringLiteral("Chat Grid — Native Qt 6 foundation"));
    resize(900, 620);
    buildMenus();
    buildCentralView();

    connect(&protocolClient_, &transport::ProtocolClient::stateChanged,
            this, &MainWindow::updateConnectionStatus);
    connect(&protocolClient_, &transport::ProtocolClient::statusMessage,
            this, &MainWindow::showStatus);
    connect(viewport_, &world::WorldViewport::viewportStatus,
            this, &MainWindow::showStatus);
    updateConnectionStatus(protocolClient_.state());
}

void MainWindow::buildMenus() {
    auto* fileMenu = menuBar()->addMenu(QStringLiteral("&File"));
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
    auto* focusWorldAction = viewMenu->addAction(QStringLiteral("Focus world viewport"));
    connect(focusWorldAction, &QAction::triggered, viewport_, [this] { viewport_->setFocus(); });
    auto* settingsAction = viewMenu->addAction(QStringLiteral("&Settings…"));
    connect(settingsAction, &QAction::triggered, this, &MainWindow::showSettings);

    auto* helpMenu = menuBar()->addMenu(QStringLiteral("&Help"));
    auto* aboutAction = helpMenu->addAction(QStringLiteral("&About Chat Grid Native Qt 6"));
    connect(aboutAction, &QAction::triggered, this, &MainWindow::showAbout);
}

void MainWindow::buildCentralView() {
    auto* root = new QWidget(this);
    auto* layout = new QVBoxLayout(root);
    auto* connectionBox = new QGroupBox(QStringLiteral("Connection"), root);
    auto* connectionLayout = new QHBoxLayout(connectionBox);
    endpointEdit_ = new QLineEdit(QStringLiteral("wss://example.invalid/chat-grid/ws"), connectionBox);
    endpointEdit_->setAccessibleName(QStringLiteral("Chat Grid server endpoint"));
    auto* connectButton = new QPushButton(QStringLiteral("Connect"), connectionBox);
    connectButton->setDefault(true);
    connect(connectButton, &QPushButton::clicked, this, &MainWindow::connectToEndpoint);
    connectionLabel_ = new QLabel(connectionBox);
    connectionLayout->addWidget(endpointEdit_, 1);
    connectionLayout->addWidget(connectButton);
    connectionLayout->addWidget(connectionLabel_);
    layout->addWidget(connectionBox);

    viewport_ = new world::WorldViewport(root);
    layout->addWidget(viewport_, 1);
    setCentralWidget(root);
    statusBar()->showMessage(QStringLiteral("Native foundation — no server connection yet."));
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
}

void MainWindow::showSettings() {
    QDialog dialog(this);
    dialog.setWindowTitle(QStringLiteral("Chat Grid Settings"));
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
    dialog.setWindowTitle(QStringLiteral("About Chat Grid Native Qt 6"));
    auto* layout = new QVBoxLayout(&dialog);
    auto* text = new QTextEdit(&dialog);
    text->setReadOnly(true);
    text->setPlainText(QStringLiteral(
        "Chat Grid native Qt 6 foundation\n\n"
        "A platform-neutral Widgets shell with native menus, status, settings, "
        "about, and a placeholder world viewport.\n\n"
        "This is not a release build. Authentication, world protocol, media, "
        "audio, packaging, and platform integration remain to be ported."));
    layout->addWidget(text);
    auto* buttons = new QDialogButtonBox(QDialogButtonBox::Close, &dialog);
    connect(buttons, &QDialogButtonBox::rejected, &dialog, &QDialog::reject);
    layout->addWidget(buttons);
    dialog.exec();
}

}  // namespace chatgrid::app
