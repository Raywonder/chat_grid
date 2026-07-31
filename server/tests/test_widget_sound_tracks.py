from types import SimpleNamespace

import pytest

from app.items.types.widget.validator import validate_update


def _item() -> SimpleNamespace:
    return SimpleNamespace(params={})


def test_widget_accepts_up_to_six_sound_references_and_loop_controls() -> None:
    refs = "||".join(f"sounds/ambience/loop-{index}.ogg" for index in range(6))
    result = validate_update(
        _item(),
        {"emitSound": refs, "emitLoopMode": "shuffle", "emitCrossfade": 2.5},
    )
    assert result["emitSound"].count("||") == 5
    assert result["emitLoopMode"] == "shuffle"
    assert result["emitCrossfade"] == 2.5


def test_widget_rejects_more_than_six_sound_references() -> None:
    refs = "||".join(f"sounds/loop-{index}.ogg" for index in range(7))
    with pytest.raises(ValueError, match="at most six"):
        validate_update(_item(), {"emitSound": refs})
