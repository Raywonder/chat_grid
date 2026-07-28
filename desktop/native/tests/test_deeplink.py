from chat_grid_native.deeplink import resolve_launch_url


def test_allows_indiginous_https_handoff():
    url = "https://blind.software/indiginous/?external_auth=opaque"
    assert resolve_launch_url([f"indiginous://connect?url={url}"]) == url


def test_keeps_legacy_chat_grid_handoff_working():
    url = "https://blind.software/chatgrid/?external_auth=opaque"
    assert resolve_launch_url([f"chatgrid://connect?url={url}"]) == url


def test_rejects_other_hosts_and_paths():
    assert resolve_launch_url(["indiginous://connect?url=https://example.com/indiginous/"]) == "https://blind.software/indiginous/"
    assert resolve_launch_url(["indiginous://connect?url=https://blind.software/account/"]) == "https://blind.software/indiginous/"
