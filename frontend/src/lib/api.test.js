import { beforeEach, describe, expect, it, vi } from 'vitest';
import i18n from '../i18n';
import {
  clearStoredMaintenanceAuth,
  extractApiError,
  getMaintenanceAuthState,
} from './api';

const DASHBOARD_AUTH_STORAGE_KEY = 'memory-palace.dashboardAuth';

describe('extractApiError', () => {
  beforeEach(async () => {
    await i18n.changeLanguage('en');
    clearStoredMaintenanceAuth();
    delete window.__MEMORY_PALACE_RUNTIME__;
    delete window.__MCP_RUNTIME_CONFIG__;
    vi.restoreAllMocks();
  });

  it('returns plain string detail directly', () => {
    const error = {
      response: {
        data: {
          detail: 'Not Found',
        },
      },
    };
    expect(extractApiError(error)).toBe('Not Found');
  });

  it('returns structured detail with error, reason, and operation', () => {
    const error = {
      response: {
        data: {
          detail: {
            error: 'index_job_enqueue_failed',
            reason: 'queue_full',
            operation: 'retry_rebuild_index',
          },
        },
      },
    };

    expect(extractApiError(error)).toBe(
      'Failed to enqueue index job | Queue is full | operation=retry_rebuild_index',
    );
  });

  it('deduplicates repeated structured fields', () => {
    const error = {
      response: {
        data: {
          detail: {
            error: 'queue_full',
            reason: 'queue_full',
            message: 'queue_full',
          },
        },
      },
    };
    expect(extractApiError(error)).toBe('Queue is full');
  });

  it('adds an actionable hint for auth failures', () => {
    const error = {
      response: {
        status: 401,
        data: {
          detail: {
            error: 'maintenance_auth_failed',
            reason: 'invalid_or_missing_api_key',
          },
        },
      },
    };
    expect(extractApiError(error)).toBe(
      'Maintenance API authentication failed | API key is missing or invalid | Click "Set API key" in the top-right corner, or configure MCP_API_KEY / MCP_API_KEY_ALLOW_INSECURE_LOCAL first.',
    );
  });

  it('returns fallback message when no structured detail exists', () => {
    const error = { message: '' };
    expect(extractApiError(error, 'fallback-message')).toBe('fallback-message');
  });

  it('localizes generic network errors in zh-CN', async () => {
    await i18n.changeLanguage('zh-CN');
    expect(extractApiError({ message: 'Network Error' })).toBe('网络异常');
  });

  it('localizes generic status-code errors in zh-CN', async () => {
    await i18n.changeLanguage('zh-CN');
    expect(extractApiError({ message: 'Request failed with status code 500' })).toBe('请求失败（状态码 500）');
  });

  it('migrates legacy dashboard auth from localStorage into sessionStorage', () => {
    window.localStorage.setItem(
      DASHBOARD_AUTH_STORAGE_KEY,
      JSON.stringify({
        maintenanceApiKey: 'legacy-key',
        maintenanceApiKeyMode: 'header',
      }),
    );

    expect(getMaintenanceAuthState()).toMatchObject({
      key: 'legacy-key',
      mode: 'header',
      source: 'stored',
    });
    expect(window.sessionStorage.getItem(DASHBOARD_AUTH_STORAGE_KEY)).toContain('legacy-key');
    expect(window.localStorage.getItem(DASHBOARD_AUTH_STORAGE_KEY)).toBeNull();
  });

  it('does not delete a newer localStorage auth value during migration', () => {
    const legacyRaw = JSON.stringify({
      maintenanceApiKey: 'legacy-key',
      maintenanceApiKeyMode: 'header',
    });
    const newerRaw = JSON.stringify({
      maintenanceApiKey: 'newer-key',
      maintenanceApiKeyMode: 'header',
    });
    const originalLocalStorage = window.localStorage;
    const originalSessionStorage = window.sessionStorage;
    let injectedNewerValue = false;

    const localStorageStore = new Map([[DASHBOARD_AUTH_STORAGE_KEY, legacyRaw]]);
    const localStorageMock = {
      getItem(key) {
        return localStorageStore.has(key) ? localStorageStore.get(key) : null;
      },
      setItem(key, value) {
        localStorageStore.set(key, String(value));
      },
      removeItem(key) {
        localStorageStore.delete(key);
      },
    };

    const sessionStorageStore = new Map();
    const sessionStorageMock = {
      getItem(key) {
        return sessionStorageStore.has(key) ? sessionStorageStore.get(key) : null;
      },
      setItem(key, value) {
        sessionStorageStore.set(key, String(value));
        if (!injectedNewerValue && key === DASHBOARD_AUTH_STORAGE_KEY) {
          injectedNewerValue = true;
          localStorageMock.setItem(DASHBOARD_AUTH_STORAGE_KEY, newerRaw);
        }
      },
      removeItem(key) {
        sessionStorageStore.delete(key);
      },
    };

    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: localStorageMock,
    });
    Object.defineProperty(window, 'sessionStorage', {
      configurable: true,
      value: sessionStorageMock,
    });

    try {
      expect(getMaintenanceAuthState()).toMatchObject({
        key: 'legacy-key',
        mode: 'header',
        source: 'stored',
      });
      expect(window.sessionStorage.getItem(DASHBOARD_AUTH_STORAGE_KEY)).toContain('legacy-key');
      expect(window.localStorage.getItem(DASHBOARD_AUTH_STORAGE_KEY)).toContain('newer-key');
    } finally {
      Object.defineProperty(window, 'localStorage', {
        configurable: true,
        value: originalLocalStorage,
      });
      Object.defineProperty(window, 'sessionStorage', {
        configurable: true,
        value: originalSessionStorage,
      });
    }
  });
});
