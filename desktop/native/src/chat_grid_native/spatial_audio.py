"""Browser-side HRTF spatial-audio runtime for compatible Chat Grid worlds."""

from __future__ import annotations

import json


BRIDGE_VERSION = 1


def spatial_audio_script(enabled: bool = True) -> str:
    """Return a self-contained, reconnect-safe Web Audio bridge."""
    enabled_js = json.dumps(bool(enabled))
    return f"""
(() => {{
  const old = window.chatGridSpatialAudio;
  if (old?.version === {BRIDGE_VERSION}) {{ old.setEnabled({enabled_js}); return; }}
  old?.dispose?.();
  const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, Number.isFinite(Number(n)) ? Number(n) : 0));
  const sources = new Map();
  let context = null;
  let enabled = {enabled_js};
  const ensureContext = () => {{
    if (!context) context = new (window.AudioContext || window.webkitAudioContext)();
    if (context.state === 'suspended') context.resume().catch(() => {{}});
    return context;
  }};
  const setPosition = (target, x, y, z) => {{
    x = clamp(x, -10000, 10000); y = clamp(y, -10000, 10000); z = clamp(z, -10000, 10000);
    if (target.positionX) {{ target.positionX.value=x; target.positionY.value=y; target.positionZ.value=z; }}
    else target.setPosition(x, y, z);
  }};
  const api = {{
    version: {BRIDGE_VERSION},
    setEnabled(value) {{
      enabled = !!value;
      for (const item of sources.values()) item.panner.panningModel = enabled ? 'HRTF' : 'equalpower';
    }},
    async unlock() {{ await ensureContext().resume(); }},
    createSource(id, mediaElement, options={{}}) {{
      if (!id || !mediaElement || sources.has(String(id))) return false;
      const ctx = ensureContext();
      const source = ctx.createMediaElementSource(mediaElement);
      const panner = ctx.createPanner();
      panner.panningModel = enabled ? 'HRTF' : 'equalpower';
      panner.distanceModel = 'inverse';
      panner.refDistance = clamp(options.refDistance ?? 1, 0.1, 1000);
      panner.maxDistance = clamp(options.maxDistance ?? 100, panner.refDistance, 10000);
      panner.rolloffFactor = clamp(options.rolloffFactor ?? 1, 0, 10);
      setPosition(panner, options.x, options.y, options.z);
      source.connect(panner).connect(ctx.destination);
      sources.set(String(id), {{source, panner}});
      return true;
    }},
    moveSource(id, x, y, z) {{
      const item = sources.get(String(id)); if (!item) return false;
      setPosition(item.panner, x, y, z); return true;
    }},
    removeSource(id) {{
      const item = sources.get(String(id)); if (!item) return false;
      try {{ item.source.disconnect(); item.panner.disconnect(); }} catch (_) {{}}
      sources.delete(String(id)); return true;
    }},
    setListener(x, y, z, forwardX=0, forwardY=0, forwardZ=-1, upX=0, upY=1, upZ=0) {{
      const listener = ensureContext().listener;
      setPosition(listener, x, y, z);
      if (listener.forwardX) {{
        listener.forwardX.value=clamp(forwardX,-1,1); listener.forwardY.value=clamp(forwardY,-1,1); listener.forwardZ.value=clamp(forwardZ,-1,1);
        listener.upX.value=clamp(upX,-1,1); listener.upY.value=clamp(upY,-1,1); listener.upZ.value=clamp(upZ,-1,1);
      }} else listener.setOrientation(forwardX,forwardY,forwardZ,upX,upY,upZ);
    }},
    dispose() {{
      for (const id of [...sources.keys()]) this.removeSource(id);
      context?.close?.().catch(() => {{}}); context = null;
    }}
  }};
  window.chatGridSpatialAudio = api;
  window.addEventListener('pagehide', () => api.dispose(), {{once:true}});
}})();
"""
