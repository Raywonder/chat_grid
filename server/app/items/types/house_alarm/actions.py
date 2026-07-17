"""House alarm item use actions."""

from __future__ import annotations

from typing import Callable

from ....item_types import ItemUseResult
from ....models import WorldItem


def _label(item: WorldItem) -> str:
    alarm_name = str(item.params.get("alarmName") or "").strip()
    return alarm_name or item.title


def _is_authorized(item: WorldItem, nickname: str) -> bool:
    names = str(item.params.get("authorizedNames") or "").split(",")
    allowed = {name.strip().casefold() for name in names if name.strip()}
    return nickname.strip().casefold() in allowed


def _code_status(item: WorldItem) -> str:
    """Return a safe spoken summary of configured in-world alarm codes."""

    code_mode = str(item.params.get("codeMode") or "off").strip().lower()
    if code_mode == "off":
        return "Codes are off."
    configured: list[str] = []
    if str(item.params.get("guestCode") or "").strip():
        configured.append("guest")
    if str(item.params.get("disarmCode") or "").strip():
        configured.append("disarm")
    if str(item.params.get("duressCode") or "").strip():
        configured.append("duress")
    if not configured:
        return f"Code mode: {code_mode}; no codes set."
    return f"Code mode: {code_mode}; configured codes: {', '.join(configured)}."


def _normalize_code_input(value: str) -> str:
    """Normalize current use credential text to the same shape as keypad codes."""

    return value.strip().replace(" ", "").replace("-", "")


def _matched_code_kind(item: WorldItem, nickname: str) -> str | None:
    """Return the in-world alarm code slot matched by the current use credential."""

    code_mode = str(item.params.get("codeMode") or "off").strip().lower()
    if code_mode == "off":
        return None
    submitted = _normalize_code_input(nickname)
    if not submitted:
        return None
    duress_code = str(item.params.get("duressCode") or "").strip()
    if duress_code and submitted == duress_code:
        return "duress"
    if code_mode in {"guest", "guest_disarm"}:
        guest_code = str(item.params.get("guestCode") or "").strip()
        if guest_code and submitted == guest_code:
            return "guest"
    if code_mode in {"disarm", "guest_disarm"}:
        disarm_code = str(item.params.get("disarmCode") or "").strip()
        if disarm_code and submitted == disarm_code:
            return "disarm"
    return None


def _notification_text(item: WorldItem) -> str:
    mode = str(item.params.get("notificationMode") or "in_grid").strip().lower()
    if mode == "in_grid":
        return "In-grid alert only."
    targets: list[str] = []
    ntfy_topic = str(item.params.get("ntfyTopic") or "").strip()
    wa_target = str(item.params.get("waNotifyTarget") or "").strip()
    if "ntfy" in mode:
        targets.append(f"ntfy topic {ntfy_topic or 'not configured'}")
    if "whatsapp" in mode:
        targets.append(f"WhatsApp target {wa_target or 'not configured'}")
    if not targets:
        return "Notification hook not configured."
    return "Notification hooks staged for " + " and ".join(targets) + "."


def evaluate_access(item: WorldItem, nickname: str, credential: str = "") -> str:
    """Return the safe access result for one resident identity or keypad entry."""

    code_kind = _matched_code_kind(item, credential)
    if code_kind:
        return code_kind
    if _is_authorized(item, nickname):
        return "authorized"
    return "denied"


def use_with_credential(
    item: WorldItem,
    nickname: str,
    credential: str,
    _clock_formatter: Callable[[dict], str],
) -> ItemUseResult:
    """Trigger or acknowledge the house alarm with a private keypad credential."""

    label = _label(item)
    house_name = str(item.params.get("houseName") or "the house").strip()
    armed_state = str(item.params.get("armedState") or "armed_home").strip().lower()
    entry_prompt = str(item.params.get("entryPrompt") or "").strip()
    alert_prompt = str(item.params.get("alertPrompt") or "").strip()
    allow_prompt = str(item.params.get("allowPrompt") or "").strip()
    notification = _notification_text(item)
    code_kind = evaluate_access(item, nickname, credential)

    if armed_state == "disarmed":
        return ItemUseResult(
            self_message=f"{label} is disarmed for {house_name}. {notification}",
            others_message=f"{nickname} checks the disarmed alarm panel for {house_name}.",
        )

    if code_kind == "disarm":
        return ItemUseResult(
            self_message=f"{label} accepts the disarm code. {house_name} is now disarmed.",
            others_message=f"{label} was disarmed by code at {house_name}.",
            updated_params={"armedState": "disarmed"},
        )

    if code_kind == "guest":
        return ItemUseResult(
            self_message=allow_prompt or f"{label} accepts the guest code. Access allowed.",
            others_message=f"{label} accepts a guest code at {house_name}.",
        )

    if code_kind == "duress":
        alert = alert_prompt or "House alarm. Someone is at the door."
        return ItemUseResult(
            self_message=allow_prompt or f"{label} accepts the code. Access allowed.",
            others_message=f"{alert} Duress code used at {house_name}.",
            updated_params={"armedState": "triggered"},
        )

    if code_kind == "authorized":
        return ItemUseResult(
            self_message=allow_prompt or f"{label} recognizes you. Access allowed.",
            others_message=f"{label} recognizes {nickname} at {house_name}.",
        )

    prompt = entry_prompt or "Please wait while the house checks whether someone can let you in."
    alert = alert_prompt or "House alarm. Someone is at the door."
    return ItemUseResult(
        self_message=f"{prompt} {notification}",
        others_message=f"{alert} Visitor: {nickname}. Location: {house_name}.",
        updated_params={"armedState": "triggered"},
        delayed_self_message="The alarm is waiting for an owner or authorized resident to allow or deny entry.",
    )


def use_item(
    item: WorldItem, nickname: str, clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Use identity-only alarm access for non-keypad clients."""

    return use_with_credential(item, nickname, nickname, clock_formatter)


def secondary_use_item(
    item: WorldItem, _nickname: str, _clock_formatter: Callable[[dict], str]
) -> ItemUseResult:
    """Speak house alarm details without triggering it."""

    label = _label(item)
    house_name = str(item.params.get("houseName") or "My house").strip()
    owner_name = str(item.params.get("ownerName") or "").strip()
    armed_state = str(item.params.get("armedState") or "armed_home").strip().lower()
    alarm_mode = str(item.params.get("alarmMode") or "entry_guard").strip().lower()
    code_hint = str(item.params.get("codeHint") or "").strip()
    description = str(item.params.get("description") or "").strip()
    parts = [
        f"{label} protects {house_name}.",
        f"Mode: {alarm_mode}.",
        f"State: {armed_state}.",
        _code_status(item),
        _notification_text(item),
    ]
    if owner_name:
        parts.append(f"Owner: {owner_name}.")
    if code_hint:
        parts.append(f"Code hint: {code_hint}.")
    if description:
        parts.append(description)
    return ItemUseResult(self_message=" ".join(parts), others_message="")
