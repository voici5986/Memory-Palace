export const DEFAULT_SSE_PATH = '/sse';

const ABSOLUTE_URL_PATTERN = /^([a-z][a-z\d+\-.]*:)?\/\//i;

const normalizeBasePath = (value) => {
  if (typeof value !== 'string') return '';
  const trimmed = value.trim();
  if (!trimmed || trimmed === '/') return '';
  return trimmed.replace(/^\/+/, '/').replace(/\/+$/, '');
};

const resolvePrefixedSsePath = (path, baseUrl) => {
  if (typeof path !== 'string' || ABSOLUTE_URL_PATTERN.test(path)) {
    return path;
  }

  const configuredApiBase = import.meta.env?.VITE_API_BASE_URL;
  if (typeof configuredApiBase !== 'string' || !configuredApiBase.trim()) {
    return path;
  }

  try {
    const originFallback =
      (typeof window !== 'undefined' && window.location?.origin) || 'http://localhost';
    const resolvedBaseUrl = new URL(String(baseUrl || originFallback).trim(), originFallback);
    const resolvedApiBase = new URL(configuredApiBase.trim(), resolvedBaseUrl);
    if (resolvedApiBase.origin !== resolvedBaseUrl.origin) {
      return path;
    }

    const normalizedApiPath = normalizeBasePath(resolvedApiBase.pathname);
    if (!normalizedApiPath.endsWith('/api')) {
      return path;
    }

    const prefix = normalizedApiPath.slice(0, -'/api'.length);
    if (!prefix) {
      return path;
    }

    return `${prefix}${path.startsWith('/') ? path : `/${path}`}`;
  } catch (_error) {
    return path;
  }
};

export const resolveSseUrl = (path = DEFAULT_SSE_PATH, baseUrl) => {
  const normalizedPath = String(path || DEFAULT_SSE_PATH).trim() || DEFAULT_SSE_PATH;
  const normalizedBaseUrl = String(
    baseUrl
      || (typeof window !== 'undefined' && window.location?.origin)
      || 'http://localhost'
  ).trim();
  const resolvedPath = resolvePrefixedSsePath(normalizedPath, normalizedBaseUrl);
  return new URL(resolvedPath, normalizedBaseUrl).toString();
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
