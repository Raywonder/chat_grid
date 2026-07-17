from __future__ import annotations

from types import SimpleNamespace

from chat_grid_native import single_instance


class FakeKernel32:
    def __init__(self, *, already_exists: bool = False) -> None:
        self.already_exists = already_exists
        self.signaled = False
        self.closed: list[int] = []

    def SetLastError(self, _value: int) -> None:
        return None

    def CreateEventW(self, *_args: object) -> int:
        return 42

    def GetLastError(self) -> int:
        return single_instance.ERROR_ALREADY_EXISTS if self.already_exists else 0

    def SetEvent(self, _handle: int) -> None:
        self.signaled = True

    def CloseHandle(self, handle: int) -> None:
        self.closed.append(handle)

    def WaitForSingleObject(self, _handle: int, _timeout: int) -> int:
        return single_instance.WAIT_OBJECT_0 if self.signaled else 258


def install_fake_windows(monkeypatch, kernel32: FakeKernel32) -> None:
    monkeypatch.setattr(single_instance.sys, "platform", "win32")
    monkeypatch.setattr(single_instance.ctypes, "windll", SimpleNamespace(kernel32=kernel32), raising=False)


def test_first_instance_owns_activation_event(monkeypatch) -> None:
    kernel32 = FakeKernel32()
    install_fake_windows(monkeypatch, kernel32)
    activation = single_instance.SingleInstanceActivation()
    assert activation.is_owner is True
    assert activation.handle == 42
    assert activation.activation_requested() is False
    activation.close()
    assert kernel32.closed == [42]


def test_second_instance_signals_owner_and_exits(monkeypatch) -> None:
    kernel32 = FakeKernel32(already_exists=True)
    install_fake_windows(monkeypatch, kernel32)
    activation = single_instance.SingleInstanceActivation()
    assert activation.is_owner is False
    assert activation.handle is None
    assert kernel32.signaled is True
    assert kernel32.closed == [42]


def test_owner_consumes_relaunch_activation(monkeypatch) -> None:
    kernel32 = FakeKernel32()
    install_fake_windows(monkeypatch, kernel32)
    activation = single_instance.SingleInstanceActivation()
    kernel32.signaled = True
    assert activation.activation_requested() is True
