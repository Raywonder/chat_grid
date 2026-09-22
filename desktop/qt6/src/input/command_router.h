#pragma once

#include <QPoint>
#include <QString>
#include <Qt>

namespace indiginous::input {

// Controls/dialogs own their keys. World commands must never be global hooks.
enum class InputContext { World, TextEditing, Dialog, Menu, MediaRemote };

struct Command {
    QString id;
    QPoint movement;
    int headingDelta = 0;
    bool reverse = false;
};

Command resolveCommand(int key, Qt::KeyboardModifiers modifiers, InputContext context);

}  // namespace indiginous::input
