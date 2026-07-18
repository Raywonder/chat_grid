from pydantic import ValidationError, TypeAdapter

from app.models import AgentVoicePacket, ClientPacket, SpeakPacket


def test_update_position_validates() -> None:
    adapter: TypeAdapter[ClientPacket] = TypeAdapter(ClientPacket)
    packet = adapter.validate_python({"type": "update_position", "x": 10, "y": 12})
    assert packet.type == "update_position"


def test_unknown_type_rejected() -> None:
    adapter: TypeAdapter[ClientPacket] = TypeAdapter(ClientPacket)
    try:
        adapter.validate_python({"type": "unknown"})
    except ValidationError:
        return
    assert False, "validation should fail"


def test_item_add_accepts_piano_type() -> None:
    adapter: TypeAdapter[ClientPacket] = TypeAdapter(ClientPacket)
    packet = adapter.validate_python({"type": "item_add", "itemType": "piano"})
    assert packet.type == "item_add"


def test_item_piano_recording_packet_validates() -> None:
    adapter: TypeAdapter[ClientPacket] = TypeAdapter(ClientPacket)
    packet = adapter.validate_python(
        {"type": "item_piano_recording", "itemId": "p1", "action": "toggle_record"}
    )
    assert packet.type == "item_piano_recording"
    stop_packet = adapter.validate_python(
        {"type": "item_piano_recording", "itemId": "p1", "action": "stop_record"}
    )
    assert stop_packet.type == "item_piano_recording"


def test_item_transfer_packet_validates() -> None:
    adapter: TypeAdapter[ClientPacket] = TypeAdapter(ClientPacket)
    packet = adapter.validate_python(
        {"type": "item_transfer", "itemId": "i1", "targetUserId": "u2"}
    )
    assert packet.type == "item_transfer"


def test_admin_user_delete_packet_validates() -> None:
    adapter: TypeAdapter[ClientPacket] = TypeAdapter(ClientPacket)
    packet = adapter.validate_python({"type": "admin_user_delete", "username": "alpha"})
    assert packet.type == "admin_user_delete"


def test_speak_packet_validates() -> None:
    adapter: TypeAdapter[ClientPacket] = TypeAdapter(ClientPacket)
    packet = adapter.validate_python(
        {"type": "speak", "audioUrl": "/voice/test.mp3", "x": 5, "y": 10}
    )
    assert isinstance(packet, SpeakPacket)
    assert packet.audioUrl == "/voice/test.mp3"
    assert packet.x == 5
    assert packet.y == 10
    assert packet.range == 20


def test_speak_packet_default_range() -> None:
    packet = SpeakPacket(type="speak", audioUrl="/voice/a.mp3", x=0, y=0)
    assert packet.range == 20


def test_speak_packet_empty_audio_url_rejected() -> None:
    adapter: TypeAdapter[ClientPacket] = TypeAdapter(ClientPacket)
    try:
        adapter.validate_python({"type": "speak", "audioUrl": "", "x": 0, "y": 0})
    except ValidationError:
        return
    assert False, "empty audioUrl should fail validation"


def test_agent_voice_packet_validates() -> None:
    packet = AgentVoicePacket(
        type="agent_voice",
        senderId="c1",
        senderNickname="Bot",
        audioUrl="/voice/out.mp3",
        x=3,
        y=7,
    )
    assert packet.type == "agent_voice"
    assert packet.range == 20
