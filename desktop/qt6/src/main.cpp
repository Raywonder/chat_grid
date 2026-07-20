#include <QApplication>

#include "app/main_window.h"

int main(int argc, char* argv[]) {
    QApplication application(argc, argv);
    application.setApplicationName(QStringLiteral("Endiginous Native Qt 6"));
    application.setOrganizationName(QStringLiteral("Divine Creations"));

    chatgrid::app::MainWindow window;
    window.show();
    return application.exec();
}
