from chat_grid_native.reconnect import ReconnectBackoff


def test_backoff_is_bounded_and_resettable() -> None:
    backoff = ReconnectBackoff(initial=2, maximum=10)
    assert [backoff.next_delay() for _ in range(5)] == [2, 4, 8, 10, 10]
    backoff.reset()
    assert backoff.next_delay() == 2
