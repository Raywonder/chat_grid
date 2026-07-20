#include "world/world_viewport.h"

#include <QPainter>
#include <QPaintEvent>

namespace chatgrid::world {

WorldViewport::WorldViewport(QWidget* parent) : QWidget(parent) {
    setFocusPolicy(Qt::StrongFocus);
    setMinimumSize(480, 320);
    setAccessibleName(QStringLiteral("Endiginous world viewport"));
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
    painter.setPen(Qt::white);
    painter.drawText(QRectF(12, 12, width() - 24, 24), Qt::AlignLeft,
                     snapshot_.locationName.isEmpty() ? QStringLiteral("World") : snapshot_.locationName);
}

}  // namespace chatgrid::world
