import { describe, expect, it, vi } from 'vitest';

import { createEventSource, resolveSseUrl } from './sse';

describe('resolveSseUrl', () => {
  it('resolves relative SSE paths against an explicit base URL', () => {
    expect(resolveSseUrl('/sse/messages', 'http://127.0.0.1:5173')).toBe(
      'http://127.0.0.1:5173/sse/messages'
    );
  });

  it('keeps absolute SSE endpoints intact', () => {
    expect(resolveSseUrl('http://127.0.0.1:8010/sse', 'http://127.0.0.1:5173')).toBe(
      'http://127.0.0.1:8010/sse'
    );
  });
});

describe('createEventSource', () => {
  it('creates an EventSource instance with resolved URL and credentials option', () => {
    const factory = vi.fn((url, init) => ({ url, init }));

    const client = createEventSource('/sse', {
      baseUrl: 'http://127.0.0.1:5173',
      withCredentials: true,
      EventSourceImpl: factory,
    });

    expect(factory).toHaveBeenCalledWith('http://127.0.0.1:5173/sse', {
      withCredentials: true,
    });
    expect(client).toEqual({
      url: 'http://127.0.0.1:5173/sse',
      init: { withCredentials: true },
    });
  });

  it('fails closed when EventSource is unavailable', () => {
    expect(() => createEventSource('/sse', { EventSourceImpl: undefined })).toThrow(
      'EventSource is not available in this environment.'
    );
  });
});
