from urllib.error import HTTPError
from urllib.request import urlopen

from chat_grid_native.browser_auth import BrowserAuthFlow


def test_browser_auth_accepts_matching_loopback_callback() -> None:
    results: list[tuple[str, str]] = []
    errors: list[str] = []
    flow = BrowserAuthFlow("https://blind.software", "https://blind.software/chatgrid/", timeout_seconds=2)
    thread = flow.start(lambda url, token: results.append((url, token)), errors.append)
    assertion = "payload.signature"
    with urlopen(f"{flow.callback_url}?state={flow.state}&assertion={assertion}") as response:
        assert response.status == 200
        assert response.headers["Cache-Control"] == "no-store"
    thread.join(2)
    assert results == [("https://blind.software/chatgrid/", assertion)]
    assert errors == []


def test_browser_auth_rejects_wrong_state() -> None:
    errors: list[str] = []
    flow = BrowserAuthFlow("https://blind.software", "https://blind.software/chatgrid/", timeout_seconds=2)
    thread = flow.start(lambda _url, _token: None, errors.append)
    try:
        urlopen(f"{flow.callback_url}?state=wrong&assertion=payload.signature")
    except HTTPError as error:
        assert error.code == 400
    thread.join(2)
    assert errors == ["The browser returned an invalid or expired Endiginous sign-in response."]


def test_browser_auth_requires_https_origin() -> None:
    try:
        BrowserAuthFlow("http://blind.software", "https://blind.software/chatgrid/")
    except ValueError:
        return
    raise AssertionError("accepted insecure browser authentication origin")
