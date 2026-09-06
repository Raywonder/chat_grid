import { describe, expect, it } from 'vitest';

import {
  TESLA_OFFICIAL_LIVE_PLAYLIST_ID,
  TESLA_OFFICIAL_YOUTUBE_CHANNEL_ID,
  resolveTrustedTvEmbedUrl,
} from './tvSourceUrl';

describe('resolveTrustedTvEmbedUrl', () => {
  it('accepts the official Tesla livestream archive playlist', () => {
    const source = `https://www.youtube.com/embed/videoseries?list=${TESLA_OFFICIAL_LIVE_PLAYLIST_ID}`;

    expect(resolveTrustedTvEmbedUrl(source)).toContain(`list=${TESLA_OFFICIAL_LIVE_PLAYLIST_ID}`);
  });

  it('accepts the official Tesla current-live endpoint', () => {
    const source = `https://www.youtube.com/embed/live_stream?channel=${TESLA_OFFICIAL_YOUTUBE_CHANNEL_ID}`;

    expect(resolveTrustedTvEmbedUrl(source)).toContain(`channel=${TESLA_OFFICIAL_YOUTUBE_CHANNEL_ID}`);
  });

  it.each([
    'https://www.youtube.com/embed/videoseries?list=PL-not-tesla',
    'https://www.youtube.com/embed/live_stream?channel=UC-not-tesla',
    `http://www.youtube.com/embed/videoseries?list=${TESLA_OFFICIAL_LIVE_PLAYLIST_ID}`,
    `https://youtube.example/embed/videoseries?list=${TESLA_OFFICIAL_LIVE_PLAYLIST_ID}`,
    'https://video.twimg.com/replayed-event.mp4',
  ])('rejects a nonofficial or non-embed source: %s', (source) => {
    expect(resolveTrustedTvEmbedUrl(source)).toBe('');
  });
});
