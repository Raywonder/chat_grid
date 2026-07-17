import Hls from 'hls.js';

import { getProxyUrlForMedia, shouldProxyExternalMediaUrl } from '../audio/mediaUrl';
import { type WorldItem } from '../state/gameState';

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
  private readonly providerLinks = document.createElement('nav');
  private readonly video = document.createElement('video');
  private hls: Hls | null = null;
  private activeItemId = '';
  private activeUrl = '';

  constructor() {
    this.region.id = 'chatgrid-tv-screen';
    this.region.setAttribute('aria-label', 'Chat Grid television');
    this.region.hidden = true;
    Object.assign(this.region.style, {
      position: 'fixed', right: '1rem', bottom: '1rem', zIndex: '20',
      width: 'min(38rem, calc(100vw - 2rem))', padding: '0.75rem',
      border: '2px solid #8fd3ff', borderRadius: '0.6rem', background: '#07131d',
      color: '#fff', boxShadow: '0 0.6rem 2rem rgba(0,0,0,.55)',
    });
    this.heading.textContent = 'Television';
    this.heading.style.margin = '0 0 .25rem';
    this.nowPlaying.id = 'chatgrid-tv-now-playing';
    this.nowPlaying.style.margin = '0 0 .5rem';
    this.video.controls = true;
    this.video.playsInline = true;
    this.video.muted = true;
    this.video.preload = 'metadata';
    this.video.setAttribute('aria-describedby', this.nowPlaying.id);
    this.video.style.width = '100%';
    this.video.style.maxHeight = '52vh';
    this.video.style.background = '#000';
    this.sourceSummary.style.margin = '0 0 .5rem';
    this.providerLinks.setAttribute('aria-label', 'TV providers');
    this.providerLinks.style.display = 'flex';
    this.providerLinks.style.gap = '.75rem';
    this.providerLinks.style.flexWrap = 'wrap';
    this.region.append(this.heading, this.nowPlaying, this.sourceSummary, this.providerLinks, this.video);
    document.body.append(this.region);
  }

  sync(items: Iterable<WorldItem>, listener: { x: number; y: number }): void {
    const selected = Array.from(items)
      .filter((item) => isTv(item) && item.params.enabled !== false)
      .map((item) => ({ item, url: playbackUrl(item), distance: Math.hypot(item.x - listener.x, item.y - listener.y) }))
      .filter(({ item, distance }) => distance <= Math.max(3, Number(item.params.emitRange) || 12))
      .sort((a, b) => a.distance - b.distance)[0];
    if (!selected) {
      this.hide();
      return;
    }
    const title = String(selected.item.params.nowPlaying || selected.item.params.stationName || selected.item.title).trim();
    this.heading.textContent = selected.item.title;
    this.nowPlaying.textContent = title ? `Now playing: ${title}` : 'TV is on.';
    this.renderSources(selected.item);
    this.region.hidden = false;
    const hasVideo = Boolean(selected.url) && looksLikeVideo(selected.item, selected.url);
    this.video.hidden = !hasVideo;
    if (!hasVideo) {
      this.stop();
      return;
    }
    if (selected.item.id === this.activeItemId && selected.url === this.activeUrl) return;
    this.load(selected.item.id, selected.url, Number(selected.item.params.playStartedAt) || 0);
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
    this.providerLinks.replaceChildren();
    const providers = Array.isArray(item.params.tvProviderSources) ? item.params.tvProviderSources : [];
    for (const entry of providers) {
      if (!entry || typeof entry !== 'object') continue;
      const record = entry as Record<string, unknown>;
      const title = String(record.title ?? '').trim();
      const url = String(record.url ?? '').trim();
      if (!title || !/^https?:\/\//i.test(url)) continue;
      const link = document.createElement('a');
      link.href = url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = `Browse ${title}`;
      link.style.color = '#8fd3ff';
      this.providerLinks.append(link);
    }
  }

  hide(): void {
    if (this.region.hidden) return;
    this.region.hidden = true;
    this.stop();
  }

  private load(itemId: string, url: string, playStartedAt: number): void {
    this.stop();
    this.activeItemId = itemId;
    this.activeUrl = url;
    const source = proxied(url);
    if (/\.m3u8(?:$|[?#])/i.test(source) && Hls.isSupported()) {
      this.hls = new Hls({ enableWorker: true, maxBufferLength: 30 });
      this.hls.loadSource(source);
      this.hls.attachMedia(this.video);
    } else {
      this.video.src = source;
    }
    this.video.addEventListener('loadedmetadata', () => {
      if (!playStartedAt || !Number.isFinite(this.video.duration) || this.video.duration <= 1) return;
      const elapsed = Math.max(0, (Date.now() - playStartedAt) / 1000);
      this.video.currentTime = Math.min(this.video.duration - 0.5, elapsed % this.video.duration);
    }, { once: true });
    void this.video.play().catch(() => {
      // Native controls remain available when autoplay requires a user gesture.
    });
  }

  private stop(): void {
    this.hls?.destroy();
    this.hls = null;
    this.video.pause();
    this.video.removeAttribute('src');
    this.video.load();
    this.activeItemId = '';
    this.activeUrl = '';
  }
}
