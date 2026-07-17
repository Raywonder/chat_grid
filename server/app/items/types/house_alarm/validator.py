"""House alarm item validation and normalization."""

from __future__ import annotations

from ....models import WorldItem
from ...helpers import keep_only_known_params
from ...sound_policy import enforce_max_length
from .definition import (
    ALARM_MODE_OPTIONS,
    ARMED_STATE_OPTIONS,
    CODE_MODE_OPTIONS,
    NOTIFICATION_MODE_OPTIONS,
    PARAM_KEYS,
)

KEYPAD_CODE_CHARS = set("0123456789*#")


def _clean_text(value: object, *, max_length: int, field_name: str) -> str:
    """Trim and length-check one editable text field."""

    return enforce_max_length(
        str(value or "").strip(), max_length=max_length, field_name=field_name
    )


def _normalize_choice(
    value: object, *, default: str, options: tuple[str, ...], field_name: str
) -> str:
    """Normalize one list-like field against allowed options."""

    candidate = str(value or default).strip().lower().replace("-", "_").replace(" ", "_")
    if field_name == "armedState":
        aliases = {
            "off": "disarmed",
            "on": "armed_home",
            "home": "armed_home",
            "away": "armed_away",
            "alarm": "triggered",
            "siren": "triggered",
        }
        candidate = aliases.get(candidate, candidate)
    elif field_name == "notificationMode":
        aliases = {
            "wa": "whatsapp",
            "whats_app": "whatsapp",
            "ntfy_wa": "ntfy_whatsapp",
            "wa_ntfy": "ntfy_whatsapp",
            "none": "in_grid",
            "local": "in_grid",
        }
        candidate = aliases.get(candidate, candidate)
    elif field_name == "codeMode":
        aliases = {
            "none": "off",
            "disabled": "off",
            "guest_only": "guest",
            "visitor": "guest",
            "visitor_code": "guest",
            "disarm_only": "disarm",
            "all": "guest_disarm",
            "both": "guest_disarm",
            "guest_and_disarm": "guest_disarm",
        }
        candidate = aliases.get(candidate, candidate)
    if candidate not in options:
        raise ValueError(f"{field_name} must be one of {', '.join(options)}.")
    return candidate


def _normalize_keypad_code(value: object, *, field_name: str) -> str:
    """Normalize one optional in-world alarm code."""

    code = str(value or "").strip().replace(" ", "").replace("-", "")
    if not code:
        return ""
    if len(code) < 3 or len(code) > 16:
        raise ValueError(f"{field_name} must be 3 to 16 keypad characters.")
    if any(char not in KEYPAD_CODE_CHARS for char in code):
        raise ValueError(f"{field_name} may contain only digits, star, and pound.")
    return code


def _ensure_distinct_codes(codes: dict[str, str]) -> None:
    """Reject duplicate non-empty code values across alarm code slots."""

    seen: dict[str, str] = {}
    for field_name, code in codes.items():
        if not code:
            continue
        existing = seen.get(code)
        if existing:
            raise ValueError(f"{field_name} must be different from {existing}.")
        seen[code] = field_name


def validate_update(_item: WorldItem, next_params: dict) -> dict:
    """Validate and normalize house alarm params."""

    next_params["alarmName"] = _clean_text(
        next_params.get("alarmName", "House alarm"),
        max_length=80,
        field_name="alarmName",
    )
    if not next_params["alarmName"]:
        next_params["alarmName"] = "House alarm"
    next_params["houseName"] = _clean_text(
        next_params.get("houseName", "My house"),
        max_length=80,
        field_name="houseName",
    )
    if not next_params["houseName"]:
        next_params["houseName"] = "My house"
    next_params["ownerName"] = _clean_text(
        next_params.get("ownerName", ""), max_length=80, field_name="ownerName"
    )
    next_params["alarmMode"] = _normalize_choice(
        next_params.get("alarmMode", "entry_guard"),
        default="entry_guard",
        options=ALARM_MODE_OPTIONS,
        field_name="alarmMode",
    )
    next_params["armedState"] = _normalize_choice(
        next_params.get("armedState", "armed_home"),
        default="armed_home",
        options=ARMED_STATE_OPTIONS,
        field_name="armedState",
    )
    next_params["codeMode"] = _normalize_choice(
        next_params.get("codeMode", "off"),
        default="off",
        options=CODE_MODE_OPTIONS,
        field_name="codeMode",
    )
    alarm_codes = {
        "guestCode": _normalize_keypad_code(
            next_params.get("guestCode", ""), field_name="guestCode"
        ),
        "disarmCode": _normalize_keypad_code(
            next_params.get("disarmCode", ""), field_name="disarmCode"
        ),
        "duressCode": _normalize_keypad_code(
            next_params.get("duressCode", ""), field_name="duressCode"
        ),
    }
    _ensure_distinct_codes(alarm_codes)
    next_params.update(alarm_codes)
    next_params["codeHint"] = _clean_text(
        next_params.get("codeHint", ""), max_length=120, field_name="codeHint"
    )
    next_params["authorizedNames"] = _clean_text(
        next_params.get("authorizedNames", ""),
        max_length=240,
        field_name="authorizedNames",
    )
    next_params["authorizedUsernames"] = _clean_text(
        next_params.get("authorizedUsernames", ""),
        max_length=240,
        field_name="authorizedUsernames",
    )
    for key in ("entryPrompt", "alertPrompt", "allowPrompt", "denyPrompt", "description"):
        next_params[key] = _clean_text(
            next_params.get(key, ""),
            max_length=240,
            field_name=key,
        )
    next_params["notificationMode"] = _normalize_choice(
        next_params.get("notificationMode", "in_grid"),
        default="in_grid",
        options=NOTIFICATION_MODE_OPTIONS,
        field_name="notificationMode",
    )
    next_params["ntfyTopic"] = _clean_text(
        next_params.get("ntfyTopic", ""),
        max_length=120,
        field_name="ntfyTopic",
    )
    next_params["waNotifyTarget"] = _clean_text(
        next_params.get("waNotifyTarget", ""),
        max_length=120,
        field_name="waNotifyTarget",
    )
    return keep_only_known_params(next_params, PARAM_KEYS)
