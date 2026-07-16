from chat_grid_native.deeplink import resolve_launch_url


def test_allows_chat_grid_https_handoff():
    url = "https://blind.software/chatgrid/?external_auth=opaque"
    assert resolve_launch_url([f"chatgrid://connect?url={url}"]) == url


def test_rejects_other_hosts_and_paths():
    assert resolve_launch_url(["chatgrid://connect?url=https://example.com/chatgrid/"]) == "https://blind.software/chatgrid/"
    assert resolve_launch_url(["chatgrid://connect?url=https://blind.software/account/"]) == "https://blind.software/chatgrid/"
