export const DEFAULT_SSE_PATH = '/sse';

export const resolveSseUrl = (path = DEFAULT_SSE_PATH, baseUrl) => {
  const normalizedPath = String(path || DEFAULT_SSE_PATH).trim() || DEFAULT_SSE_PATH;
  const normalizedBaseUrl = String(
    baseUrl
      || (typeof window !== 'undefined' && window.location?.origin)
      || 'http://localhost'
  ).trim();
  return new URL(normalizedPath, normalizedBaseUrl).toString();
};

/**
 * @typedef {{
 *   baseUrl?: string,
 *   withCredentials?: boolean,
 *   EventSourceImpl?: typeof EventSource,
 * }} CreateEventSourceOptions
 */

/**
 * @param {string} path
 * @param {CreateEventSourceOptions} [options]
 */
export const createEventSource = (
  path = DEFAULT_SSE_PATH,
  options = {}
) => {
  const {
    baseUrl,
    withCredentials = false,
    EventSourceImpl = globalThis.EventSource,
  } = options;
  if (typeof EventSourceImpl !== 'function') {
    throw new Error('EventSource is not available in this environment.');
  }

  const url = resolveSseUrl(path, baseUrl);
  return new EventSourceImpl(url, { withCredentials });
};
