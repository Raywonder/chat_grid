#include "world/world_viewport.h"

#include <QPainter>
#include <QPaintEvent>
#include <QKeyEvent>
#include <QFocusEvent>
#include <QJsonArray>
#include <QApplication>
#include <cmath>

namespace indiginous::world {

WorldViewport::WorldViewport(QWidget* parent) : QWidget(parent) {
    setFocusPolicy(Qt::StrongFocus);
    setMinimumSize(480, 320);
    setAccessibleName(QStringLiteral("Indiginous world viewport"));
    setAccessibleDescription(QStringLiteral("Native placeholder for the future server-authoritative world view."));
}

const WorldSnapshot& WorldViewport::snapshot() const noexcept {
    return snapshot_;
}

void WorldViewport::applySnapshot(const WorldSnapshot& snapshot) {
    snapshot_ = snapshot;
    hasSnapshot_ = true;
    update();
    emit viewportStatus(QStringLiteral("Location: %1; grid: %2 by %2.")
                            .arg(snapshot_.locationName.isEmpty() ? QStringLiteral("unknown") : snapshot_.locationName)
                            .arg(snapshot_.gridSize));
}

void WorldViewport::applyWelcome(const QJsonObject& welcome) {
    headingDegrees_ = 0;
    WorldSnapshot next;
    const QJsonObject world = welcome.value("worldConfig").toObject();
    const QJsonObject player = welcome.value("player").toObject();
    next.gridSize = qMax(1, world.value("gridSize").toInt(20));
    next.gridWidth = qMax(1, world.value("gridWidth").toInt(next.gridSize));
    next.gridHeight = qMax(1, world.value("gridHeight").toInt(next.gridSize));
    next.playerId = welcome.value("id").toString(player.value("id").toString());
    next.locationId = world.value("locationId").toString(player.value("locationId").toString("city"));
    next.locationName = world.value("locationName").toString(next.locationId);
    next.playerPosition = QPointF(player.value("x").toInt(), player.value("y").toInt());
    for (const QJsonValue& value : welcome.value("users").toArray()) {
        const QJsonObject user = value.toObject();
        const auto id = user.value("id").toString();
        if (!id.isEmpty() && id != next.playerId)
            next.otherPlayers.insert(id, QPointF(user.value("x").toInt(), user.value("y").toInt()));
    }
    applySnapshot(next);
}

void WorldViewport::applyPosition(const QJsonObject& position) {
    if (!hasSnapshot_) return;
    const auto id = position.value("id").toString();
    const auto location = position.value("locationId").toString();
    if (id.isEmpty() || (!location.isEmpty() && location != snapshot_.locationId)) return;
    const auto x = position.value("x");
    const auto y = position.value("y");
    if (!x.isDouble() || !y.isDouble()) return;
    const double px = x.toDouble(), py = y.toDouble();
    if (!std::isfinite(px) || !std::isfinite(py) || std::floor(px) != px || std::floor(py) != py) return;
    if (px < 0 || py < 0 || px >= snapshot_.gridWidth || py >= snapshot_.gridHeight) return;
    if (id == snapshot_.playerId) snapshot_.playerPosition = QPointF(px, py);
    else snapshot_.otherPlayers.insert(id, QPointF(px, py));
    update();
}

void WorldViewport::clearSnapshot() {
    hasSnapshot_ = false;
    snapshot_ = WorldSnapshot{};
    headingDegrees_ = 0;
    update();
    emit viewportStatus(QStringLiteral("No world snapshot loaded."));
}

void WorldViewport::applyLocation(const QJsonObject& location) {
    if (!hasSnapshot_ || location.value("id").toString() != snapshot_.playerId) return;
    const QString id = location.value("locationId").toString();
    if (id.isEmpty()) return;
    const int width = location.value("width").toInt(snapshot_.gridWidth);
    const int height = location.value("height").toInt(snapshot_.gridHeight);
    const auto x = location.value("x"), y = location.value("y");
    if (!x.isDouble() || !y.isDouble() || width <= 0 || height <= 0) return;
    if (std::floor(x.toDouble()) != x.toDouble() || std::floor(y.toDouble()) != y.toDouble()) return;
    if (x.toDouble() < 0 || y.toDouble() < 0 || x.toDouble() >= width || y.toDouble() >= height) return;
    snapshot_.locationId = id;
    snapshot_.locationName = location.value("locationName").toString(id);
    snapshot_.gridWidth = width;
    snapshot_.gridHeight = height;
    snapshot_.playerPosition = QPointF(x.toDouble(), y.toDouble());
    snapshot_.otherPlayers.clear();
    update();
    emit viewportStatus(QStringLiteral("Location: %1.").arg(snapshot_.locationName));
}

void WorldViewport::paintEvent(QPaintEvent* event) {
    Q_UNUSED(event)
    QPainter painter(this);
    painter.fillRect(rect(), QColor(QStringLiteral("#101820")));
    painter.setRenderHint(QPainter::Antialiasing, false);

    const int gridWidth = qMax(1, snapshot_.gridWidth);
    const int gridHeight = qMax(1, snapshot_.gridHeight);
    const qreal cell = qMin(width() / static_cast<qreal>(gridWidth), height() / static_cast<qreal>(gridHeight));
    const qreal offsetX = (width() - cell * gridWidth) / 2.0;
    const qreal offsetY = (height() - cell * gridHeight) / 2.0;
    painter.setPen(QPen(QColor(QStringLiteral("#2a4352")), 1));
    for (int i = 0; i <= gridWidth; ++i) {
        painter.drawLine(QPointF(offsetX + i * cell, offsetY),
                         QPointF(offsetX + i * cell, offsetY + gridHeight * cell));
    }
    for (int i = 0; i <= gridHeight; ++i) {
        painter.drawLine(QPointF(offsetX, offsetY + i * cell),
                         QPointF(offsetX + gridWidth * cell, offsetY + i * cell));
    }

    if (!hasSnapshot_) {
        painter.setPen(Qt::white);
        painter.drawText(rect(), Qt::AlignCenter,
                         QStringLiteral("Native world viewport\nWaiting for a server snapshot"));
        return;
    }

    painter.setBrush(QColor(QStringLiteral("#59d6a1")));
    painter.setPen(Qt::NoPen);
    const QPointF player(offsetX + snapshot_.playerPosition.x() * cell,
                          offsetY + snapshot_.playerPosition.y() * cell);
    painter.drawEllipse(player, qMax<qreal>(4.0, cell * 0.25), qMax<qreal>(4.0, cell * 0.25));
    painter.setBrush(QColor(QStringLiteral("#e8b45f")));
    for (const QPointF& remote : snapshot_.otherPlayers) {
        painter.drawEllipse(QPointF(offsetX + remote.x() * cell, offsetY + remote.y() * cell),
                            qMax<qreal>(3.0, cell * 0.18), qMax<qreal>(3.0, cell * 0.18));
    }
    painter.setPen(Qt::white);
    painter.drawText(QRectF(12, 12, width() - 24, 24), Qt::AlignLeft,
                     snapshot_.locationName.isEmpty() ? QStringLiteral("World") : snapshot_.locationName);
}

void WorldViewport::keyPressEvent(QKeyEvent* event) {
    if (!hasSnapshot_ || !hasFocus() || QApplication::activeModalWidget()) { event->ignore(); return; }
    const auto command = input::resolveCommand(event->key(), event->modifiers(), inputContext_);
    if (command.id.isEmpty()) { event->ignore(); return; }
    if (command.id == QStringLiteral("move")) {
        const QPointF next = snapshot_.playerPosition + command.movement;
        if (next.x() >= 0 && next.y() >= 0 && next.x() < snapshot_.gridWidth && next.y() < snapshot_.gridHeight)
            emit moveRequested(qRound(next.x()), qRound(next.y()));
        // Only server updates advance the displayed position. No local gameplay rule.
    } else if (!event->isAutoRepeat()) {
        if (command.id == QStringLiteral("turn")) {
            headingDegrees_ = (headingDegrees_ + command.headingDelta + 360) % 360;
            emit viewportStatus(QStringLiteral("Heading: %1 degrees.").arg(headingDegrees_));
        } else if (command.id == QStringLiteral("speakCoordinates")) {
            emit viewportStatus(QStringLiteral("Coordinates: %1, %2.").arg(snapshot_.playerPosition.x()).arg(snapshot_.playerPosition.y()));
        } else if (command.id == QStringLiteral("speakLocation")) {
            emit viewportStatus(snapshot_.locationName);
        } else {
            emit commandRequested(command.id, command.reverse);
        }
    }
    event->accept();
}

bool WorldViewport::event(QEvent* event) {
    // QWidget normally consumes Tab for focus traversal before keyPressEvent.
    if (event->type() == QEvent::KeyPress && hasFocus() && hasSnapshot_
        && inputContext_ == input::InputContext::World && !QApplication::activeModalWidget()) {
        auto* key = static_cast<QKeyEvent*>(event);
        if ((key->key() == Qt::Key_Tab || key->key() == Qt::Key_Backtab)
            && !(key->modifiers() & (Qt::ControlModifier | Qt::AltModifier | Qt::MetaModifier))) {
            keyPressEvent(key);
            return key->isAccepted();
        }
    }
    return QWidget::event(event);
}

void WorldViewport::focusInEvent(QFocusEvent* event) {
    QWidget::focusInEvent(event);
    if (!focusedOnce_) {
        focusedOnce_ = true;
        emit viewportStatus(QStringLiteral("World is ready for keyboard input."));
    }
}

}  // namespace indiginous::world
