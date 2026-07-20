import { afterEach, describe, expect, it, vi } from 'vitest';
import { SignalingClient } from './signalingClient';

describe('SignalingClient.send', () => {
  const originalWebSocket = globalThis.WebSocket;

  afterEach(() => {
    globalThis.WebSocket = originalWebSocket;
  });

  it('turns a close/send race into a retryable false result', () => {
    globalThis.WebSocket = { OPEN: 1 } as unknown as typeof WebSocket;
    const status = vi.fn();
    const client = new SignalingClient('wss://example.invalid', status);
    const socket = {
      readyState: 1,
      send: vi.fn(() => {
        throw new Error('socket closed during send');
      }),
    };
    (client as unknown as { ws: typeof socket }).ws = socket;

    const sent = client.send({ type: 'chat_message', message: 'hello' });

    expect(sent).toBe(false);
    expect(socket.send).toHaveBeenCalledOnce();
    expect(status).toHaveBeenCalledWith('Connection interrupted; message queued for reconnect.');
  });
});
