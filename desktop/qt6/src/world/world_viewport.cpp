#include "world/world_viewport.h"

#include <QPainter>
#include <QPaintEvent>
#include <QKeyEvent>
#include <QFocusEvent>
#include <QJsonArray>

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
    WorldSnapshot next;
    const QJsonObject world = welcome.value("worldConfig").toObject();
    const QJsonObject player = welcome.value("player").toObject();
    next.gridSize = qMax(1, world.value("gridSize").toInt(20));
    next.locationId = world.value("locationId").toString(player.value("locationId").toString("city"));
    next.locationName = world.value("locationName").toString(next.locationId);
    next.playerPosition = QPointF(player.value("x").toInt(), player.value("y").toInt());
    for (const QJsonValue& value : welcome.value("users").toArray()) {
        const QJsonObject user = value.toObject();
        next.otherPlayers.append(QPointF(user.value("x").toInt(), user.value("y").toInt()));
    }
    applySnapshot(next);
}

void WorldViewport::clearSnapshot() {
    hasSnapshot_ = false;
    update();
    emit viewportStatus(QStringLiteral("No world snapshot loaded."));
}

void WorldViewport::paintEvent(QPaintEvent* event) {
    Q_UNUSED(event)
    QPainter painter(this);
    painter.fillRect(rect(), QColor(QStringLiteral("#101820")));
    painter.setRenderHint(QPainter::Antialiasing, false);

    const int gridSize = qMax(1, snapshot_.gridSize);
    const qreal cell = qMin(width(), height()) / static_cast<qreal>(gridSize);
    const qreal offsetX = (width() - cell * gridSize) / 2.0;
    const qreal offsetY = (height() - cell * gridSize) / 2.0;
    painter.setPen(QPen(QColor(QStringLiteral("#2a4352")), 1));
    for (int i = 0; i <= gridSize; ++i) {
        painter.drawLine(QPointF(offsetX + i * cell, offsetY),
                         QPointF(offsetX + i * cell, offsetY + gridSize * cell));
        painter.drawLine(QPointF(offsetX, offsetY + i * cell),
                         QPointF(offsetX + gridSize * cell, offsetY + i * cell));
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
    if (!hasSnapshot_) { event->ignore(); return; }
    QPointF next = snapshot_.playerPosition;
    switch (event->key()) {
    case Qt::Key_Left: case Qt::Key_A: --next.rx(); break;
    case Qt::Key_Right: case Qt::Key_D: ++next.rx(); break;
    case Qt::Key_Up: case Qt::Key_W: --next.ry(); break;
    case Qt::Key_Down: case Qt::Key_S: ++next.ry(); break;
    default: event->ignore(); return;
    }
    const int maxX = qMax(0, snapshot_.gridSize - 1);
    const int maxY = qMax(0, snapshot_.gridSize - 1);
    next.setX(qBound(0.0, next.x(), static_cast<qreal>(maxX)));
    next.setY(qBound(0.0, next.y(), static_cast<qreal>(maxY)));
    snapshot_.playerPosition = next;
    update();
    emit moveRequested(qRound(next.x()), qRound(next.y()));
    event->accept();
}

void WorldViewport::focusInEvent(QFocusEvent* event) {
    QWidget::focusInEvent(event);
    if (!focusedOnce_) {
        focusedOnce_ = true;
        emit viewportStatus(QStringLiteral("World is ready for keyboard input."));
    }
}

}  // namespace indiginous::world
