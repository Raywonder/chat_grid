#pragma once

#include <QPointF>
#include <QJsonObject>
#include <QString>
#include <QWidget>
#include <QVector>
#include <QMap>
#include "input/command_router.h"

class QFocusEvent;
class QKeyEvent;

namespace indiginous::world {

struct WorldSnapshot {
    int gridSize = 20;
    int gridWidth = 20;
    int gridHeight = 20;
    QString playerId;
    QString locationId;
    QString locationName;
    QPointF playerPosition{0.0, 0.0};
    QMap<QString, QPointF> otherPlayers;
};

class WorldViewport final : public QWidget {
    Q_OBJECT

public:
    explicit WorldViewport(QWidget* parent = nullptr);

    const WorldSnapshot& snapshot() const noexcept;
    int headingDegrees() const noexcept { return headingDegrees_; }
    void setInputContext(input::InputContext context) { inputContext_ = context; }

public slots:
    void applySnapshot(const WorldSnapshot& snapshot);
    void applyWelcome(const QJsonObject& welcome);
    void applyPosition(const QJsonObject& position);
    void applyLocation(const QJsonObject& location);
    void clearSnapshot();

signals:
    void viewportStatus(const QString& message);
    void moveRequested(int x, int y);
    void commandRequested(const QString& id, bool reverse);

protected:
    void paintEvent(QPaintEvent* event) override;

private:
    WorldSnapshot snapshot_;
    bool hasSnapshot_ = false;
    bool focusedOnce_ = false;
    int headingDegrees_ = 0;
    input::InputContext inputContext_ = input::InputContext::World;

protected:
    void keyPressEvent(QKeyEvent* event) override;
    bool event(QEvent* event) override;
    void focusInEvent(QFocusEvent* event) override;
};

}  // namespace indiginous::world
