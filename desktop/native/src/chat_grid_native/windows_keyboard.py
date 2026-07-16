"""Foreground-only Windows arrow-key hook for the embedded world."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from typing import Callable


WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
VK_CONTROL = 0x11
VK_MENU = 0x12
ARROW_KEYS = {0x25, 0x26, 0x27, 0x28}


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class WindowsWorldKeyHook:
    """Capture arrows before WebView/screen-reader browse-mode processing."""

    def __init__(self, on_arrow: Callable[[int], None]) -> None:
        self.on_arrow = on_arrow
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32
        self.hook = None
        result_type = ctypes.c_ssize_t
        self.proc_type = ctypes.WINFUNCTYPE(
            result_type, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t
        )
        self.proc = self.proc_type(self._callback)

        self.user32.SetWindowsHookExW.restype = wintypes.HHOOK
        self.user32.SetWindowsHookExW.argtypes = (
            ctypes.c_int,
            self.proc_type,
            wintypes.HINSTANCE,
            wintypes.DWORD,
        )
        self.kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        self.kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
        self.user32.CallNextHookEx.restype = result_type
        self.hook = self.user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, self.proc, self.kernel32.GetModuleHandleW(None), 0
        )
        if not self.hook:
            raise OSError(ctypes.get_last_error(), "Unable to install Chat Grid keyboard hook")

    def _is_foreground_process(self) -> bool:
        hwnd = self.user32.GetForegroundWindow()
        if not hwnd:
            return False
        process_id = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        return process_id.value == os.getpid()

    def _modifier_down(self, virtual_key: int) -> bool:
        return bool(self.user32.GetAsyncKeyState(virtual_key) & 0x8000)

    def _callback(self, code: int, message: int, data_address: int) -> int:
        if code == HC_ACTION and message in {WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP}:
            data = ctypes.cast(
                data_address, ctypes.POINTER(KBDLLHOOKSTRUCT)
            ).contents
            if (
                data.vkCode in ARROW_KEYS
                and self._is_foreground_process()
                and not self._modifier_down(VK_CONTROL)
                and not self._modifier_down(VK_MENU)
            ):
                if message == WM_KEYDOWN:
                    self.on_arrow(int(data.vkCode))
                return 1
        return int(self.user32.CallNextHookEx(self.hook, code, message, data_address))

    def close(self) -> None:
        if self.hook:
            self.user32.UnhookWindowsHookEx(self.hook)
            self.hook = None
