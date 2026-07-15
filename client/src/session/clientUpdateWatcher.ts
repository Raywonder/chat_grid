export type ClientVersionMetadata = {
  releaseVersion: string;
  clientRevision: string;
  entrypointUrl?: string;
};

type ClientUpdateWatcherOptions = {
  currentRevision: string;
  currentEntrypointUrl?: string;
  versionUrl: string;
  indexUrl: string;
  pollMs: number;
  onUpdateAvailable: (metadata: ClientVersionMetadata) => void;
};

const VERSION_FETCH_TIMEOUT_MS = 5_000;

function parseClientVersionMetadata(text: string): ClientVersionMetadata {
  const releaseMatch = text.match(/CHGRID_RELEASE_VERSION\s*=\s*"([^"]+)"/);
  const revisionMatch = text.match(/CHGRID_CLIENT_REVISION\s*=\s*"([^"]+)"/);
  return {
    releaseVersion: releaseMatch?.[1]?.trim() ?? '',
    clientRevision: revisionMatch?.[1]?.trim() ?? '',
  };
}

async function fetchClientVersionMetadata(versionUrl: string): Promise<ClientVersionMetadata | null> {
  const url = new URL(versionUrl, window.location.href);
  url.searchParams.set('_', String(Date.now()));
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), VERSION_FETCH_TIMEOUT_MS);
  try {
    const response = await fetch(url.toString(), {
      cache: 'no-store',
      headers: {
        'Cache-Control': 'no-cache',
        Pragma: 'no-cache',
      },
      signal: controller.signal,
    });
    if (!response.ok) return null;
    return parseClientVersionMetadata(await response.text());
  } catch {
    return null;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function normalizeEntrypointUrl(value: string | undefined): string {
  if (!value) return '';
  try {
    const url = new URL(value, window.location.href);
    return `${url.pathname}${url.search}`;
  } catch {
    return '';
  }
}

function parseIndexEntrypointUrl(text: string, indexUrl: string): string {
  const match = text.match(/<script\b[^>]*\btype=["']module["'][^>]*\bsrc=["']([^"']+)["'][^>]*>/i)
    ?? text.match(/<script\b[^>]*\bsrc=["']([^"']+)["'][^>]*\btype=["']module["'][^>]*>/i);
  if (!match?.[1]) return '';
  try {
    const url = new URL(match[1], new URL(indexUrl, window.location.href));
    return `${url.pathname}${url.search}`;
  } catch {
    return '';
  }
}

async function fetchLiveEntrypointUrl(indexUrl: string): Promise<string> {
  const url = new URL(indexUrl, window.location.href);
  url.searchParams.set('_', String(Date.now()));
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), VERSION_FETCH_TIMEOUT_MS);
  try {
    const response = await fetch(url.toString(), {
      cache: 'no-store',
      headers: {
        'Cache-Control': 'no-cache',
        Pragma: 'no-cache',
      },
      signal: controller.signal,
    });
    if (!response.ok) return '';
    return parseIndexEntrypointUrl(await response.text(), indexUrl);
  } catch {
    return '';
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export function startClientUpdateWatcher(options: ClientUpdateWatcherOptions): () => void {
  let disposed = false;
  let checkInFlight = false;
  let updateHandled = false;
  const currentEntrypointUrl = normalizeEntrypointUrl(options.currentEntrypointUrl);

  const checkForUpdate = async (): Promise<void> => {
    if (disposed || checkInFlight || updateHandled) return;
    checkInFlight = true;
    try {
      const [metadata, liveEntrypointUrl] = await Promise.all([
        fetchClientVersionMetadata(options.versionUrl),
        currentEntrypointUrl ? fetchLiveEntrypointUrl(options.indexUrl) : Promise.resolve(''),
      ]);
      const revisionChanged = !!metadata?.clientRevision && metadata.clientRevision !== options.currentRevision;
      const entrypointChanged = !!liveEntrypointUrl && liveEntrypointUrl !== currentEntrypointUrl;
      if (!revisionChanged && !entrypointChanged) return;
      updateHandled = true;
      options.onUpdateAvailable({
        releaseVersion: metadata?.releaseVersion ?? '',
        clientRevision: metadata?.clientRevision ?? '',
        entrypointUrl: liveEntrypointUrl || undefined,
      });
    } finally {
      checkInFlight = false;
    }
  };

  const handleVisibilityChange = (): void => {
    if (document.visibilityState === 'visible') {
      void checkForUpdate();
    }
  };

  const intervalId = window.setInterval(() => {
    if (document.visibilityState === 'visible') {
      void checkForUpdate();
    }
  }, Math.max(5_000, options.pollMs));

  window.addEventListener('focus', checkForUpdate);
  window.addEventListener('online', checkForUpdate);
  window.addEventListener('pageshow', checkForUpdate);
  document.addEventListener('visibilitychange', handleVisibilityChange);
  void checkForUpdate();

  return () => {
    disposed = true;
    window.clearInterval(intervalId);
    window.removeEventListener('focus', checkForUpdate);
    window.removeEventListener('online', checkForUpdate);
    window.removeEventListener('pageshow', checkForUpdate);
    document.removeEventListener('visibilitychange', handleVisibilityChange);
  };
}
