"""Piano item validation/normalization."""

from __future__ import annotations

from ....models import WorldItem
from ...helpers import keep_only_known_params
from .definition import (
    DEFAULT_ENVELOPE_BY_INSTRUMENT,
    INSTRUMENT_OPTIONS,
    PARAM_KEYS,
    VOICE_MODE_OPTIONS,
)


def validate_update(item: WorldItem, next_params: dict) -> dict:
    """Validate and normalize piano params."""

    # Song references are server-managed and not directly editable from client updates.
    preserved_song_id = item.params.get("songId")
    next_params.pop("songId", None)

    instrument = str(next_params.get("instrument", "piano")).strip().lower()
    if instrument not in INSTRUMENT_OPTIONS:
        raise ValueError(f"instrument must be one of: {', '.join(INSTRUMENT_OPTIONS)}.")
    previous_instrument = str(item.params.get("instrument", "piano")).strip().lower()
    next_params["instrument"] = instrument

    voice_mode = (
        str(next_params.get("voiceMode", item.params.get("voiceMode", "poly")))
        .strip()
        .lower()
    )
    if voice_mode not in VOICE_MODE_OPTIONS:
        raise ValueError("voiceMode must be one of: poly, mono.")
    next_params["voiceMode"] = voice_mode

    try:
        octave = int(next_params.get("octave", item.params.get("octave", 0)))
    except (TypeError, ValueError) as exc:
        raise ValueError("octave must be an integer between -2 and 2.") from exc
    if not (-2 <= octave <= 2):
        raise ValueError("octave must be between -2 and 2.")
    next_params["octave"] = octave

    try:
        attack = int(next_params.get("attack", 15))
    except (TypeError, ValueError) as exc:
        raise ValueError("attack must be an integer between 0 and 100.") from exc
    if not (0 <= attack <= 100):
        raise ValueError("attack must be between 0 and 100.")
    try:
        decay = int(next_params.get("decay", 45))
    except (TypeError, ValueError) as exc:
        raise ValueError("decay must be an integer between 0 and 100.") from exc
    if not (0 <= decay <= 100):
        raise ValueError("decay must be between 0 and 100.")

    try:
        release = int(next_params.get("release", 35))
    except (TypeError, ValueError) as exc:
        raise ValueError("release must be an integer between 0 and 100.") from exc
    if not (0 <= release <= 100):
        raise ValueError("release must be between 0 and 100.")

    try:
        brightness = int(next_params.get("brightness", 55))
    except (TypeError, ValueError) as exc:
        raise ValueError("brightness must be an integer between 0 and 100.") from exc
    if not (0 <= brightness <= 100):
        raise ValueError("brightness must be between 0 and 100.")

    # When instrument changes, reset envelope to instrument-appropriate defaults.
    if instrument != previous_instrument:
        attack, decay, release, brightness, voice_mode, octave = (
            DEFAULT_ENVELOPE_BY_INSTRUMENT.get(instrument, (15, 45, 35, 55, "poly", 0))
        )
        next_params["voiceMode"] = voice_mode
        next_params["octave"] = octave
    next_params["attack"] = attack
    next_params["decay"] = decay
    next_params["release"] = release
    next_params["brightness"] = brightness

    try:
        emit_range = int(next_params.get("emitRange", 15))
    except (TypeError, ValueError) as exc:
        raise ValueError("emitRange must be an integer between 5 and 20.") from exc
    if not (5 <= emit_range <= 20):
        raise ValueError("emitRange must be between 5 and 20.")
    next_params["emitRange"] = emit_range

    if isinstance(preserved_song_id, str) and preserved_song_id.strip():
        next_params["songId"] = preserved_song_id.strip()

    return keep_only_known_params(next_params, PARAM_KEYS)
