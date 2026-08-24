#pragma once

#include <QPointF>
#include <QJsonObject>
#include <QString>
#include <QWidget>
#include <QVector>

class QFocusEvent;
class QKeyEvent;

namespace indiginous::world {

struct WorldSnapshot {
    int gridSize = 20;
    QString locationId;
    QString locationName;
    QPointF playerPosition{0.0, 0.0};
    QVector<QPointF> otherPlayers;
};

class WorldViewport final : public QWidget {
    Q_OBJECT

public:
    explicit WorldViewport(QWidget* parent = nullptr);

    const WorldSnapshot& snapshot() const noexcept;

public slots:
    void applySnapshot(const WorldSnapshot& snapshot);
    void applyWelcome(const QJsonObject& welcome);
    void clearSnapshot();

signals:
    void viewportStatus(const QString& message);
    void moveRequested(int x, int y);

protected:
    void paintEvent(QPaintEvent* event) override;

private:
    WorldSnapshot snapshot_;
    bool hasSnapshot_ = false;
    bool focusedOnce_ = false;

protected:
    void keyPressEvent(QKeyEvent* event) override;
    void focusInEvent(QFocusEvent* event) override;
};

}  // namespace indiginous::world
