import Hls from 'hls.js';

import { getProxyUrlForMedia, shouldProxyExternalMediaUrl } from '../audio/mediaUrl';
import { type WorldItem } from '../state/gameState';
import { resolveTrustedTvEmbedUrl } from './tvSourceUrl';

const VIDEO_EXTENSIONS = /\.(?:mp4|m4v|mov|webm|mkv|m3u8)(?:$|[?#])/i;

function isTv(item: WorldItem): boolean {
  return item.type === 'house_object' && String(item.params.objectKind ?? '').trim().toLowerCase() === 'tv';
}

function playbackUrl(item: WorldItem): string {
  return String(item.params.playbackUrl || item.params.streamUrl || '').trim();
}

function looksLikeVideo(item: WorldItem, url: string): boolean {
  const mediaKind = String(item.params.mediaKind ?? item.params.sourceType ?? '').trim().toLowerCase();
  return ['video', 'movie', 'episode'].includes(mediaKind) || VIDEO_EXTENSIONS.test(url);
}

function proxied(url: string): string {
  return shouldProxyExternalMediaUrl(url) ? getProxyUrlForMedia(url) : url;
}

/** Shows the nearest active TV picture while program audio remains spatial. */
export class TvScreenRuntime {
  private readonly region = document.createElement('section');
  private readonly heading = document.createElement('h2');
  private readonly nowPlaying = document.createElement('p');
  private readonly sourceSummary = document.createElement('p');
  private readonly video = document.createElement('video');
  private readonly embed = document.createElement('iframe');
  private hls: Hls | null = null;
  private activeItemId = '';
  private activeUrl = '';
  private pendingJellyfinItemId = '';
  private programSegments: Array<{ url: string; kind: string; title?: string }> = [];
  private programSegmentIndex = 0;

  setJellyfinPlaybackRequester(requester: ((mediaKind: 'tv' | 'radio', itemId: string) => void) | null): void {
    this.jellyfinPlaybackRequester = requester;
  }

  private jellyfinPlaybackRequester: ((mediaKind: 'tv' | 'radio', itemId: string) => void) | null = null;

  constructor() {
    this.region.id = 'indiginous-tv-screen';
    this.region.setAttribute('aria-label', 'Indiginous television');
    this.region.hidden = true;
    Object.assign(this.region.style, {
      position: 'fixed', right: '1rem', bottom: '1rem', zIndex: '20',
      width: 'min(38rem, calc(100vw - 2rem))', padding: '0.75rem',
      border: '2px solid #8fd3ff', borderRadius: '0.6rem', background: '#07131d',
      color: '#fff', boxShadow: '0 0.6rem 2rem rgba(0,0,0,.55)',
    });
    this.heading.textContent = 'Television';
    this.heading.style.margin = '0 0 .25rem';
    this.nowPlaying.id = 'indiginous-tv-now-playing';
    this.nowPlaying.style.margin = '0 0 .5rem';
    this.video.controls = true;
    this.video.playsInline = true;
    this.video.muted = true;
    this.video.preload = 'metadata';
    this.video.setAttribute('aria-describedby', this.nowPlaying.id);
    this.video.style.width = '100%';
    this.video.style.maxHeight = '52vh';
    this.video.style.background = '#000';
    this.embed.hidden = true;
    this.embed.title = 'Tesla TV official livestream player';
    this.embed.allow = 'autoplay; encrypted-media; picture-in-picture';
    this.embed.allowFullscreen = true;
    this.embed.referrerPolicy = 'strict-origin-when-cross-origin';
    this.embed.sandbox.add('allow-scripts', 'allow-same-origin', 'allow-presentation');
    Object.assign(this.embed.style, {
      width: '100%', aspectRatio: '16 / 9', maxHeight: '52vh', border: '0', background: '#000',
    });
    this.embed.setAttribute('aria-describedby', this.nowPlaying.id);
    this.sourceSummary.style.margin = '0 0 .5rem';
    this.region.append(this.heading, this.nowPlaying, this.sourceSummary, this.video, this.embed);
    document.body.append(this.region);
  }

  sync(items: Iterable<WorldItem>, listener: { x: number; y: number }): void {
    const televisions = Array.from(items)
      .filter((item) => isTv(item) && item.params.enabled !== false)
      .map((item) => ({ item, url: playbackUrl(item), distance: Math.hypot(item.x - listener.x, item.y - listener.y) }));
    const selected = televisions
      .filter(({ item, distance }) => distance <= Math.max(3, Number(item.params.emitRange) || 12))
      .sort((a, b) => a.distance - b.distance)[0];
    if (!selected) {
      // Keep the shared TV media element playing while it is out of range.
      // The picture is hidden, but returning to the room can reuse the same
      // continuous playback position instead of restarting the programme.
      const activeStillExists = this.activeItemId.length > 0 && televisions.some(({ item, url }) =>
        item.id === this.activeItemId && Boolean(url)
          && (Boolean(resolveTrustedTvEmbedUrl(url)) || looksLikeVideo(item, url)),
      );
      if (activeStillExists) {
        this.region.hidden = true;
      } else {
        this.hide();
      }
      return;
    }
    const title = String(selected.item.params.nowPlaying || selected.item.params.stationName || selected.item.title).trim();
    this.heading.textContent = selected.item.title;
    this.nowPlaying.textContent = title ? `Now playing: ${title}` : 'TV is on.';
    this.renderSources(selected.item);
    this.region.hidden = false;
    const embedUrl = resolveTrustedTvEmbedUrl(selected.url);
    const hasVideo = Boolean(selected.url) && looksLikeVideo(selected.item, selected.url);
    const jellyfinItemId = String(selected.item.params.jellyfinItemId ?? '').trim();
    if (!selected.url && jellyfinItemId && this.pendingJellyfinItemId !== jellyfinItemId) {
      this.pendingJellyfinItemId = jellyfinItemId;
      this.jellyfinPlaybackRequester?.('tv', jellyfinItemId);
    }
    this.video.hidden = !hasVideo;
    this.embed.hidden = !embedUrl;
    if (!embedUrl && !hasVideo) {
      if (jellyfinItemId) return;
      this.stop();
      return;
    }
    if (selected.item.id === this.activeItemId && selected.url === this.activeUrl) return;
    if (embedUrl) {
      this.loadEmbed(selected.item.id, selected.url, embedUrl);
      return;
    }
    const segments = Array.isArray(selected.item.params.jellyfinSegments)
      ? selected.item.params.jellyfinSegments.filter((entry): entry is { url: string; kind: string; title?: string } =>
        Boolean(entry) && typeof entry === 'object' && typeof (entry as Record<string, unknown>).url === 'string',
      )
      : [];
    this.load(selected.item.id, selected.url, Number(selected.item.params.playStartedAt) || 0, segments);
  }

  private renderSources(item: WorldItem): void {
    const libraries = Array.isArray(item.params.tvLibrarySources) ? item.params.tvLibrarySources : [];
    const libraryNames = libraries
      .filter((entry): entry is Record<string, unknown> => Boolean(entry) && typeof entry === 'object')
      .map((entry) => String(entry.title ?? '').trim())
      .filter(Boolean);
    this.sourceSummary.textContent = libraryNames.length > 0
      ? `Libraries: ${libraryNames.join(', ')}.`
      : '';
  }

  hide(): void {
    if (this.region.hidden) return;
    this.region.hidden = true;
    this.stop();
  }

  private loadEmbed(itemId: string, rawUrl: string, embedUrl: string): void {
    this.stop();
    this.activeItemId = itemId;
    this.activeUrl = rawUrl;
    this.embed.src = embedUrl;
    this.embed.hidden = false;
  }

  private load(itemId: string, url: string, playStartedAt: number, segments: Array<{ url: string; kind: string; title?: string }> = []): void {
    this.stop();
    this.activeItemId = itemId;
    this.activeUrl = url;
    this.pendingJellyfinItemId = '';
    this.programSegments = segments.length > 0 ? segments.filter((segment) => segment.url.trim()) : [{ url, kind: 'content' }];
    this.programSegmentIndex = 0;
    this.playProgramSegment(playStartedAt);
  }

  private playProgramSegment(playStartedAt: number): void {
    const segment = this.programSegments[this.programSegmentIndex];
    if (!segment) return;
    const source = proxied(segment.url);
    if (/\.m3u8(?:$|[?#])/i.test(source) && Hls.isSupported()) {
      this.hls = new Hls({ enableWorker: true, maxBufferLength: 30 });
      this.hls.loadSource(source);
      this.hls.attachMedia(this.video);
    } else {
      this.video.src = proxied(segment.url);
    }
    this.video.addEventListener('loadedmetadata', () => {
      if (!playStartedAt || !Number.isFinite(this.video.duration) || this.video.duration <= 1) return;
      const elapsed = Math.max(0, (Date.now() - playStartedAt) / 1000);
      this.video.currentTime = Math.min(this.video.duration - 0.5, elapsed % this.video.duration);
    }, { once: true });
    void this.video.play().catch(() => {
      // Native controls remain available when autoplay requires a user gesture.
    });
    this.video.onended = () => {
      if (this.programSegmentIndex + 1 >= this.programSegments.length) return;
      this.programSegmentIndex += 1;
      this.playProgramSegment(0);
    };
  }

  private stop(): void {
    this.hls?.destroy();
    this.hls = null;
    this.video.pause();
    this.video.removeAttribute('src');
    this.video.load();
    this.embed.removeAttribute('src');
    this.embed.hidden = true;
    this.activeItemId = '';
    this.activeUrl = '';
    this.programSegments = [];
    this.programSegmentIndex = 0;
    this.video.onended = null;
  }
}
