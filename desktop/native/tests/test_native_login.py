from chat_grid_native.app import MainFrame


def test_server_url_accepts_domain_and_uses_chatgrid_path():
    assert MainFrame._server_url("example.com") == "https://example.com/chatgrid/"


def test_server_url_preserves_https_port_but_not_user_path():
    assert MainFrame._server_url("https://grid.example:8443/anything") == "https://grid.example:8443/chatgrid/"


def test_server_url_rejects_insecure_or_credentialed_urls():
    for value in ("http://example.com", "https://user@example.com", ""):
        try:
            MainFrame._server_url(value)
        except ValueError:
            continue
        raise AssertionError(f"accepted unsafe server value: {value}")
