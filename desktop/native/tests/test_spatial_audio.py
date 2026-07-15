from chat_grid_native.spatial_audio import BRIDGE_VERSION, spatial_audio_script


def test_spatial_audio_bridge_is_versioned_and_uses_hrtf():
    script = spatial_audio_script(True)
    assert f"version: {BRIDGE_VERSION}" in script
    assert "'HRTF'" in script
    assert "createPanner" in script
    assert "setListener" in script


def test_spatial_audio_bridge_supports_fallback_and_cleanup():
    script = spatial_audio_script(False)
    assert "let enabled = false" in script
    assert "'equalpower'" in script
    assert "pagehide" in script
    assert "dispose()" in script
