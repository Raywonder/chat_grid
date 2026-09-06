export const TESLA_OFFICIAL_YOUTUBE_CHANNEL_ID = 'UC5WjFrtBdufl6CZojX3D8dQ';
export const TESLA_OFFICIAL_LIVE_PLAYLIST_ID = 'UULV5WjFrtBdufl6CZojX3D8dQ';

const TRUSTED_YOUTUBE_HOSTS = new Set(['www.youtube.com', 'youtube.com']);

/** Returns an embeddable URL only for Tesla's verified YouTube live sources. */
export function resolveTrustedTvEmbedUrl(rawUrl: string): string {
  let parsed: URL;
  try {
    parsed = new URL(rawUrl);
  } catch {
    return '';
  }
  if (parsed.protocol !== 'https:' || !TRUSTED_YOUTUBE_HOSTS.has(parsed.hostname.toLowerCase())) {
    return '';
  }
  const isOfficialLivePlaylist = parsed.pathname === '/embed/videoseries'
    && parsed.searchParams.get('list') === TESLA_OFFICIAL_LIVE_PLAYLIST_ID;
  const isOfficialCurrentLive = parsed.pathname === '/embed/live_stream'
    && parsed.searchParams.get('channel') === TESLA_OFFICIAL_YOUTUBE_CHANNEL_ID;
  if (!isOfficialLivePlaylist && !isOfficialCurrentLive) return '';

  parsed.searchParams.set('autoplay', '1');
  parsed.searchParams.set('mute', '1');
  parsed.searchParams.set('playsinline', '1');
  return parsed.toString();
}
