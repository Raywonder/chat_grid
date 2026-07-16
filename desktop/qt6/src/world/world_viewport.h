#pragma once

#include <QPointF>
#include <QString>
#include <QWidget>

namespace chatgrid::world {

struct WorldSnapshot {
    int gridSize = 20;
    QString locationId;
    QString locationName;
    QPointF playerPosition{0.0, 0.0};
};

class WorldViewport final : public QWidget {
    Q_OBJECT

public:
    explicit WorldViewport(QWidget* parent = nullptr);

    const WorldSnapshot& snapshot() const noexcept;

public slots:
    void applySnapshot(const WorldSnapshot& snapshot);
    void clearSnapshot();

signals:
    void viewportStatus(const QString& message);

protected:
    void paintEvent(QPaintEvent* event) override;

private:
    WorldSnapshot snapshot_;
    bool hasSnapshot_ = false;
};

}  // namespace chatgrid::world
