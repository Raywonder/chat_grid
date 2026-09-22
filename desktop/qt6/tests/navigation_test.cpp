#include <QtTest>
#include <QLineEdit>
#include <QVBoxLayout>
#include <QWebSocketServer>
#include <QJsonDocument>
#include "input/command_router.h"
#include "world/world_viewport.h"
#include "transport/protocol_client.h"

using indiginous::input::InputContext;
using indiginous::input::resolveCommand;
using indiginous::world::WorldViewport;

static QJsonObject welcome() {
    return {{"type", "welcome"}, {"id", "self"},
            {"worldConfig", QJsonObject{{"gridSize", 20}, {"gridWidth", 30}, {"gridHeight", 12}, {"locationId", "room"}}},
            {"player", QJsonObject{{"x", 5}, {"y", 6}}}};
}

class NavigationTest final : public QObject {
    Q_OBJECT
private slots:
    void commandContexts() {
        for (auto context : {InputContext::TextEditing, InputContext::Dialog, InputContext::Menu}) {
            QVERIFY(resolveCommand(Qt::Key_Left, Qt::NoModifier, context).id.isEmpty());
            QVERIFY(resolveCommand(Qt::Key_A, Qt::NoModifier, context).id.isEmpty());
        }
        QCOMPARE(resolveCommand(Qt::Key_A, Qt::NoModifier, InputContext::World).id, QString("addItem"));
        QCOMPARE(resolveCommand(Qt::Key_D, Qt::NoModifier, InputContext::World).id, QString("pickupDropItem"));
        QCOMPARE(resolveCommand(Qt::Key_D, Qt::ShiftModifier, InputContext::World).id, QString("pickupDropAttachedItems"));
        QVERIFY(resolveCommand(Qt::Key_W, Qt::NoModifier, InputContext::World).id.isEmpty());
        QVERIFY(resolveCommand(Qt::Key_S, Qt::NoModifier, InputContext::World).id.isEmpty());
        QCOMPARE(resolveCommand(Qt::Key_Right, Qt::ShiftModifier, InputContext::World).headingDelta, 15);
        QCOMPARE(resolveCommand(Qt::Key_Left, Qt::ShiftModifier, InputContext::World).headingDelta, -15);
        QVERIFY(resolveCommand(Qt::Key_Up, Qt::ShiftModifier, InputContext::World).id.isEmpty());
        QCOMPARE(resolveCommand(Qt::Key_Left, Qt::ControlModifier, InputContext::World).id, QString("radioRemoteStationPrevious"));
        QVERIFY(resolveCommand(Qt::Key_Up, Qt::ControlModifier, InputContext::World).id.isEmpty());
        for (auto modifier : {Qt::AltModifier, Qt::MetaModifier})
            QVERIFY(resolveCommand(Qt::Key_Left, modifier, InputContext::World).id.isEmpty());
        QCOMPARE(resolveCommand(Qt::Key_Up, Qt::NoModifier, InputContext::MediaRemote).id, QString("radioRemoteVolumeUp"));
        QVERIFY(resolveCommand(Qt::Key_Left, Qt::ShiftModifier, InputContext::MediaRemote).movement.isNull());
        QCOMPARE(resolveCommand(Qt::Key_M, Qt::ControlModifier, InputContext::World).id, QString("openDirectMessage"));
        QVERIFY(resolveCommand(Qt::Key_Backtab, Qt::NoModifier, InputContext::World).reverse);
    }

    void nativeKeysAndAuthoritativePosition() {
        QWidget host;
        QVBoxLayout layout(&host);
        WorldViewport viewport;
        QLineEdit edit;
        layout.addWidget(&viewport);
        layout.addWidget(&edit);
        host.show(); host.activateWindow(); viewport.setFocus();
        QTRY_VERIFY(viewport.hasFocus());
        viewport.applyWelcome(welcome());
        QSignalSpy moves(&viewport, &WorldViewport::moveRequested);
        QSignalSpy commands(&viewport, &WorldViewport::commandRequested);
        QTest::keyClick(&viewport, Qt::Key_Right);
        QCOMPARE(moves.count(), 1);
        QCOMPARE(moves.at(0).at(0).toInt(), 6);
        QCOMPARE(viewport.snapshot().playerPosition, QPointF(5, 6));
        viewport.applyPosition({{"id", "self"}, {"locationId", "room"}, {"x", 4}, {"y", 6}});
        QCOMPARE(viewport.snapshot().playerPosition, QPointF(4, 6));
        QTest::keyClick(&viewport, Qt::Key_Right);
        QCOMPARE(moves.at(1).at(0).toInt(), 5);
        QTest::keyClick(&viewport, Qt::Key_A);
        QTest::keyClick(&viewport, Qt::Key_D);
        QCOMPARE(moves.count(), 2);
        QCOMPARE(commands.at(0).at(0).toString(), QString("addItem"));
        QCOMPARE(commands.at(1).at(0).toString(), QString("pickupDropItem"));
        QTest::keyClick(&viewport, Qt::Key_Left, Qt::ShiftModifier);
        QCOMPARE(viewport.headingDegrees(), 345);
        QCOMPARE(moves.count(), 2);
        QTest::keyClick(&viewport, Qt::Key_Up, Qt::ShiftModifier);
        QTest::keyClick(&viewport, Qt::Key_Up, Qt::ControlModifier);
        QTest::keyClick(&viewport, Qt::Key_Left, Qt::AltModifier);
        QCOMPARE(moves.count(), 2);
        QTest::keyClick(&viewport, Qt::Key_Tab);
        QCOMPARE(commands.last().at(0).toString(), QString("cycleFocusedItem"));
        QVERIFY(viewport.hasFocus());
        viewport.setInputContext(InputContext::MediaRemote);
        QTest::keyClick(&viewport, Qt::Key_Up);
        QCOMPARE(commands.last().at(0).toString(), QString("radioRemoteVolumeUp"));
        QCOMPARE(moves.count(), 2);
        edit.setFocus(); QTRY_VERIFY(edit.hasFocus());
        QTest::keyClicks(&edit, "ad");
        QTest::keyClick(&edit, Qt::Key_Left);
        QCOMPARE(edit.text(), QString("ad"));
        QCOMPARE(moves.count(), 2);
        viewport.setInputContext(InputContext::World);
        viewport.setFocus(); QTRY_VERIFY(viewport.hasFocus());
        viewport.applyPosition({{"id", "self"}, {"x", 29}, {"y", 11}});
        QTest::keyClick(&viewport, Qt::Key_Right);
        QTest::keyClick(&viewport, Qt::Key_Down);
        QCOMPARE(moves.count(), 2);
        viewport.clearSnapshot(); viewport.setFocus();
        QTest::keyClick(&viewport, Qt::Key_Right);
        QCOMPARE(moves.count(), 2);
    }

    void packetIdentityAndValidation() {
        WorldViewport viewport;
        viewport.applyWelcome(welcome());
        viewport.applyPosition({{"id", "peer"}, {"x", 8}, {"y", 9}});
        QCOMPARE(viewport.snapshot().playerPosition, QPointF(5, 6));
        QCOMPARE(viewport.snapshot().otherPlayers.value("peer"), QPointF(8, 9));
        viewport.applyPosition({{"id", "self"}, {"locationId", "other"}, {"x", 2}, {"y", 2}});
        viewport.applyPosition({{"x", 2}, {"y", 2}});
        viewport.applyPosition({{"id", "self"}, {"x", "invalid"}, {"y", 2}});
        viewport.applyPosition({{"id", "self"}, {"x", 2.5}, {"y", 2}});
        viewport.applyPosition({{"id", "self"}, {"x", 2}, {"y", 12}});
        QCOMPARE(viewport.snapshot().playerPosition, QPointF(5, 6));
        viewport.applyPosition({{"id", "self"}, {"x", 29}, {"y", 11}});
        QCOMPARE(viewport.snapshot().playerPosition, QPointF(29, 11));
        viewport.clearSnapshot();
        viewport.applyPosition({{"id", "self"}, {"x", 1}, {"y", 1}});
        QCOMPARE(viewport.snapshot().playerPosition, QPointF(0, 0));
    }

    void websocketPositionRetainsIdentity() {
        QWebSocketServer server(QStringLiteral("synthetic-test"), QWebSocketServer::NonSecureMode);
        QVERIFY(server.listen(QHostAddress::LocalHost, 0));
        indiginous::transport::ProtocolClient client;
        WorldViewport viewport;
        connect(&client, &indiginous::transport::ProtocolClient::welcomeReceived, &viewport, &WorldViewport::applyWelcome);
        connect(&client, &indiginous::transport::ProtocolClient::positionReceived, &viewport, &WorldViewport::applyPosition);
        client.connectToServer(QString("ws://127.0.0.1:%1").arg(server.serverPort()));
        QTRY_VERIFY(server.hasPendingConnections());
        auto* peer = server.nextPendingConnection();
        QVERIFY(peer);
        auto send = [peer](const QJsonObject& object) { peer->sendTextMessage(QString::fromUtf8(QJsonDocument(object).toJson())); };
        send(welcome());
        QTRY_COMPARE(viewport.snapshot().playerId, QString("self"));
        send({{"type", "update_position"}, {"id", "peer"}, {"x", 7}, {"y", 8}});
        QTRY_COMPARE(viewport.snapshot().otherPlayers.value("peer"), QPointF(7, 8));
        QCOMPARE(viewport.snapshot().playerPosition, QPointF(5, 6));
        send({{"type", "update_position"}, {"id", "self"}, {"x", 6}, {"y", 6}});
        QTRY_COMPARE(viewport.snapshot().playerPosition, QPointF(6, 6));
        client.disconnectFromServer();
        peer->deleteLater();
    }

    void locationIdentityAndDimensions() {
        WorldViewport viewport;
        viewport.applyWelcome(welcome());
        QJsonObject location{{"id", "peer"}, {"locationId", "small"}, {"width", 4}, {"height", 3}, {"x", 3}, {"y", 2}};
        viewport.applyLocation(location);
        QCOMPARE(viewport.snapshot().locationId, QString("room"));
        location["id"] = "self";
        viewport.applyLocation(location);
        QCOMPARE(viewport.snapshot().locationId, QString("small"));
        QCOMPARE(viewport.snapshot().gridWidth, 4);
        QCOMPARE(viewport.snapshot().gridHeight, 3);
        QCOMPARE(viewport.snapshot().playerPosition, QPointF(3, 2));
        location["x"] = 5;
        viewport.applyLocation(location);
        QCOMPARE(viewport.snapshot().playerPosition, QPointF(3, 2));
    }
};

QTEST_MAIN(NavigationTest)
#include "navigation_test.moc"
