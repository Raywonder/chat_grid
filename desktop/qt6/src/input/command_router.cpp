#include "input/command_router.h"

namespace indiginous::input {

Command resolveCommand(int key, Qt::KeyboardModifiers modifiers, InputContext context) {
    if (context != InputContext::World && context != InputContext::MediaRemote) return {};
    if (modifiers & (Qt::AltModifier | Qt::MetaModifier)) return {};
    const bool shift = modifiers.testFlag(Qt::ShiftModifier);
    const bool ctrl = modifiers.testFlag(Qt::ControlModifier);
    auto named = [shift](const char* id) { return Command{QString::fromLatin1(id), {}, 0, shift}; };

    // A focused media remote owns arrows; never also walk or turn.
    if (context == InputContext::MediaRemote) {
        if (key == Qt::Key_Up) return named("radioRemoteVolumeUp");
        if (key == Qt::Key_Down) return named("radioRemoteVolumeDown");
        if (!shift && key == Qt::Key_Left) return named("radioRemoteStationPrevious");
        if (!shift && key == Qt::Key_Right) return named("radioRemoteStationNext");
        if (key == Qt::Key_Left || key == Qt::Key_Right) return {};
    }
    if (ctrl) {
        if (key == Qt::Key_M) return named("openDirectMessage");
        if (key == Qt::Key_R) return named("openUserActionMenu");
        if (key == Qt::Key_G) return named("listLocations");
        if (key == Qt::Key_K) return named("openCommandPalette");
        if (key == Qt::Key_Right) return named("radioRemoteStationNext");
        if (key == Qt::Key_Left) return named("radioRemoteStationPrevious");
        if (shift && (key == Qt::Key_Up || key == Qt::Key_U)) return named("radioRemoteVolumeUp");
        if (shift && (key == Qt::Key_Down || key == Qt::Key_D)) return named("radioRemoteVolumeDown");
        return {};
    }
    if (shift && (key == Qt::Key_Left || key == Qt::Key_Right))
        return {QStringLiteral("turn"), {}, key == Qt::Key_Left ? -15 : 15, false};
    if (!shift) {
        switch (key) {
        case Qt::Key_Left: return {QStringLiteral("move"), {-1, 0}};
        case Qt::Key_Right: return {QStringLiteral("move"), {1, 0}};
        case Qt::Key_Up: return {QStringLiteral("move"), {0, -1}};
        case Qt::Key_Down: return {QStringLiteral("move"), {0, 1}};
        default: break;
        }
    }
    // Canonical semantic IDs match mainCommandRouter.ts, not WASD conventions.
    switch (key) {
    case Qt::Key_A: return shift ? Command{} : named("addItem");
    case Qt::Key_D: return named(shift ? "pickupDropAttachedItems" : "pickupDropItem");
    case Qt::Key_I: return named(shift ? "listItems" : "locateNearestItem");
    case Qt::Key_L: return named(shift ? "listUsers" : "locateNearestUser");
    case Qt::Key_G: return named("listLocations");
    case Qt::Key_C: return shift ? Command{} : named("speakCoordinates");
    case Qt::Key_Y: return shift ? Command{} : named("speakLocation");
    case Qt::Key_U: return shift ? Command{} : named("speakUsers");
    case Qt::Key_H: return named(shift ? "allowNearbyUser" : "openChat");
    case Qt::Key_Slash: case Qt::Key_Question: return named(shift ? "openHelp" : "openChat");
    case Qt::Key_N: return named(shift ? "openNotifications" : "editNickname");
    case Qt::Key_M: return named(shift ? "toggleOutputMode" : "toggleMute");
    case Qt::Key_R: return shift ? named("openUserActionMenu") : Command{};
    case Qt::Key_O: return named(shift ? "inspectItem" : "editItem");
    case Qt::Key_Z: return named(shift ? "openAdminMenu" : "openItemManagement");
    case Qt::Key_Tab: return named("cycleFocusedItem");
    case Qt::Key_Backtab: return {QStringLiteral("cycleFocusedItem"), {}, 0, true};
    case Qt::Key_Return: case Qt::Key_Enter: return named(shift ? "interactItem" : "useItem");
    case Qt::Key_Space: return named(shift ? "radioRemoteStationPrevious" : "useItem");
    case Qt::Key_Comma: case Qt::Key_Less: return named(shift ? "chatFirst" : "chatPrev");
    case Qt::Key_Period: case Qt::Key_Greater: return named(shift ? "chatLast" : "chatNext");
    case Qt::Key_Escape: return named(shift ? "leaveWorldControls" : "escape");
    case Qt::Key_K: return shift ? named("openCommandPalette") : Command{};
    case Qt::Key_Menu: return named("openCommandPalette");
    case Qt::Key_F10: return shift ? named("openCommandPalette") : Command{};
    default: return {};
    }
}

}  // namespace indiginous::input
