import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { render, screen, waitFor, within } from '@testing-library/react';

import App, { buildRoutesKey, resolveAppBasename } from './App';
import i18n, { LOCALE_STORAGE_KEY } from './i18n';

const { memoryMountCounter, setupApi } = vi.hoisted(() => ({
  memoryMountCounter: { current: 0 },
  setupApi: {
    getSetupStatus: vi.fn(),
    saveSetupConfig: vi.fn(),
  },
}));

vi.mock('./lib/api', async () => {
  const actual = await vi.importActual('./lib/api');
  return {
    ...actual,
    getSetupStatus: setupApi.getSetupStatus,
    saveSetupConfig: setupApi.saveSetupConfig,
  };
});

vi.mock('./features/memory/MemoryBrowser', () => ({
  default: () => {
    React.useEffect(() => {
      memoryMountCounter.current += 1;
    }, []);
    return <div>memory-page</div>;
  },
}));

vi.mock('./features/review/ReviewPage', () => ({
  default: () => <div>review-page</div>,
}));

vi.mock('./features/maintenance/MaintenancePage', () => ({
  default: () => <div>maintenance-page</div>,
}));

vi.mock('./features/observability/ObservabilityPage', () => ({
  default: () => <div>observability-page</div>,
}));

describe('App routing', () => {
  beforeEach(async () => {
    memoryMountCounter.current = 0;
    window.localStorage?.removeItem?.('memory-palace.dashboardAuth');
    window.sessionStorage?.removeItem?.('memory-palace.dashboardAuth');
    window.localStorage?.removeItem?.(LOCALE_STORAGE_KEY);
    window.localStorage?.setItem?.('memory-palace.setupAssistantDismissed', '1');
    delete document.documentElement.dataset.browserProfile;
    delete window.__MEMORY_PALACE_RUNTIME__;
    await i18n.changeLanguage('en');
    window.localStorage?.removeItem?.(LOCALE_STORAGE_KEY);
    setupApi.getSetupStatus.mockReset();
    setupApi.saveSetupConfig.mockReset();
    setupApi.getSetupStatus.mockResolvedValue({
      ok: true,
      apply_supported: true,
      apply_reason: 'local_env_file',
      target_label: '.env',
      restart_required: true,
      restart_targets: ['backend', 'sse'],
      summary: {
        dashboard_auth_configured: false,
        allow_insecure_local: false,
        embedding_backend: 'hash',
        embedding_configured: true,
        reranker_enabled: false,
        reranker_configured: false,
        write_guard_enabled: false,
        write_guard_configured: false,
        intent_llm_enabled: false,
        intent_llm_configured: false,
      },
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    window.history.pushState({}, '', '/');
  });

  it('redirects root path to memory', async () => {
    window.history.pushState({}, '', '/');

    render(<App />);

    expect(await screen.findByText('memory-page')).toBeInTheDocument();
    await waitFor(() => expect(window.location.pathname).toBe('/memory'));
  });

  it('redirects unknown paths to memory', async () => {
    window.history.pushState({}, '', '/unknown-route');

    render(<App />);

    expect(await screen.findByText('memory-page')).toBeInTheDocument();
    await waitFor(() => expect(window.location.pathname).toBe('/memory'));
  });

  it('derives a router basename from a same-origin prefixed API base', () => {
    vi.stubEnv('BASE_URL', '/');
    vi.stubEnv('VITE_API_BASE_URL', '/memory-palace/api/');

    expect(resolveAppBasename()).toBe('/memory-palace');
  });

  it('keeps redirects inside the resolved app basename', async () => {
    vi.stubEnv('BASE_URL', '/');
    vi.stubEnv('VITE_API_BASE_URL', '/memory-palace/api/');
    window.history.pushState({}, '', '/memory-palace/');

    render(<App />);

    expect(await screen.findByText('memory-page')).toBeInTheDocument();
    await waitFor(() => expect(window.location.pathname).toBe('/memory-palace/memory'));
  });

  it('stores API key through header action when runtime config is absent', async () => {
    const user = userEvent.setup();
    window.history.pushState({}, '', '/memory');

    render(<App />);

    await user.click(screen.getByRole('button', { name: i18n.t('app.auth.setApiKey') }));
    const dialog = await screen.findByRole('dialog', { name: i18n.t('setup.title') });
    await user.type(
      within(dialog).getByPlaceholderText(i18n.t('setup.dashboard.apiKeyPlaceholder')),
      'stored-key'
    );
    await user.click(screen.getByRole('button', { name: i18n.t('setup.actions.saveBrowserOnly') }));

    expect(window.sessionStorage.getItem('memory-palace.dashboardAuth')).toContain('stored-key');
    expect(await screen.findByRole('button', { name: i18n.t('app.auth.updateApiKey') })).toBeInTheDocument();
  });

  it('keeps browser-only dashboard auth across remounts until it is cleared', async () => {
    const user = userEvent.setup();
    window.history.pushState({}, '', '/memory');

    const firstRender = render(<App />);

    await user.click(screen.getByRole('button', { name: i18n.t('app.auth.setApiKey') }));
    const dialog = await screen.findByRole('dialog', { name: i18n.t('setup.title') });
    await user.type(
      within(dialog).getByPlaceholderText(i18n.t('setup.dashboard.apiKeyPlaceholder')),
      'stored-key'
    );
    await user.click(screen.getByRole('button', { name: i18n.t('setup.actions.saveBrowserOnly') }));

    expect(await screen.findByRole('button', { name: i18n.t('app.auth.updateApiKey') })).toBeInTheDocument();

    firstRender.unmount();
    render(<App />);

    expect(await screen.findByRole('button', { name: i18n.t('app.auth.updateApiKey') })).toBeInTheDocument();
  });

  it('shows a browser-storage risk warning inside the setup assistant', async () => {
    const user = userEvent.setup();
    window.history.pushState({}, '', '/memory');

    render(<App />);

    await user.click(screen.getByRole('button', { name: i18n.t('app.auth.setApiKey') }));
    expect(
      await screen.findByText(/Avoid saving this key in shared browsers or profiles you do not control\./i)
    ).toBeInTheDocument();
  });

  it('shows an error instead of crashing when browser storage rejects the API key write', async () => {
    const user = userEvent.setup();
    const originalStorage = window.sessionStorage;
    window.history.pushState({}, '', '/memory');

    render(<App />);

    await user.click(screen.getByRole('button', { name: i18n.t('app.auth.setApiKey') }));
    const dialog = await screen.findByRole('dialog', { name: i18n.t('setup.title') });
    await user.type(
      within(dialog).getByPlaceholderText(i18n.t('setup.dashboard.apiKeyPlaceholder')),
      'stored-key'
    );
    Object.defineProperty(window, 'sessionStorage', {
      configurable: true,
      writable: true,
      value: {
        getItem: originalStorage.getItem.bind(originalStorage),
        setItem: (key, value) => {
          if (key === 'memory-palace.dashboardAuth') {
            throw new Error('quota');
          }
          return originalStorage.setItem(key, value);
        },
        removeItem: originalStorage.removeItem.bind(originalStorage),
        clear: originalStorage.clear.bind(originalStorage),
      },
    });

    await user.click(screen.getByRole('button', { name: i18n.t('setup.actions.saveBrowserOnly') }));
    Object.defineProperty(window, 'sessionStorage', {
      configurable: true,
      writable: true,
      value: originalStorage,
    });

    expect((await screen.findAllByText(i18n.t('setup.messages.saveFailed'))).length).toBeGreaterThan(0);
    expect(screen.getByRole('dialog', { name: i18n.t('setup.title') })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: i18n.t('app.auth.setApiKey') })).toBeInTheDocument();
  });

  it('shows an error instead of a false success when server save succeeds but browser auth persistence fails', async () => {
    const user = userEvent.setup();
    const originalStorage = window.sessionStorage;
    window.history.pushState({}, '', '/memory');
    setupApi.saveSetupConfig.mockResolvedValueOnce({
      ok: true,
      target_label: '.env',
      restart_targets: ['backend', 'sse'],
    });

    render(<App />);

    await user.click(screen.getByRole('button', { name: i18n.t('app.auth.setApiKey') }));
    const dialog = await screen.findByRole('dialog', { name: i18n.t('setup.title') });
    await user.type(
      within(dialog).getByPlaceholderText(i18n.t('setup.dashboard.apiKeyPlaceholder')),
      'stored-key'
    );

    Object.defineProperty(window, 'sessionStorage', {
      configurable: true,
      writable: true,
      value: {
        getItem: originalStorage.getItem.bind(originalStorage),
        setItem: (key, value) => {
          if (key === 'memory-palace.dashboardAuth') {
            throw new Error('quota');
          }
          return originalStorage.setItem(key, value);
        },
        removeItem: originalStorage.removeItem.bind(originalStorage),
        clear: originalStorage.clear.bind(originalStorage),
      },
    });

    try {
      await user.click(screen.getByRole('button', { name: i18n.t('setup.actions.saveEnv') }));

      expect((await screen.findAllByText(i18n.t('setup.messages.saveFailed'))).length).toBeGreaterThan(0);
      expect(screen.queryByText(i18n.t('setup.messages.serverSaved', { target: '.env' }))).not.toBeInTheDocument();
      expect(screen.getByRole('dialog', { name: i18n.t('setup.title') })).toBeInTheDocument();
      expect(window.sessionStorage.getItem('memory-palace.dashboardAuth')).toBeNull();
      expect(setupApi.saveSetupConfig).toHaveBeenCalledTimes(1);
    } finally {
      Object.defineProperty(window, 'sessionStorage', {
        configurable: true,
        writable: true,
        value: originalStorage,
      });
    }
  });

  it('remounts routes after stored auth changes without depending on raw key text', async () => {
    const user = userEvent.setup();
    window.history.pushState({}, '', '/memory');

    render(<App />);
    expect(await screen.findByText('memory-page')).toBeInTheDocument();
    await waitFor(() => expect(memoryMountCounter.current).toBe(1));

    await user.click(screen.getByRole('button', { name: i18n.t('app.auth.setApiKey') }));
    const dialog = await screen.findByRole('dialog', { name: i18n.t('setup.title') });
    await user.type(
      within(dialog).getByPlaceholderText(i18n.t('setup.dashboard.apiKeyPlaceholder')),
      'stored-key'
    );
    await user.click(screen.getByRole('button', { name: i18n.t('setup.actions.saveBrowserOnly') }));

    await waitFor(() => expect(memoryMountCounter.current).toBe(2));
  });

  it('defaults to english when no stored locale exists', async () => {
    window.history.pushState({}, '', '/memory');

    render(<App />);

    expect(await screen.findByRole('button', { name: 'Set API key' })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe('en');
  });

  it('shows runtime status badge when runtime config is present', async () => {
    window.history.pushState({}, '', '/memory');
    window.__MEMORY_PALACE_RUNTIME__ = {
      maintenanceApiKey: 'runtime-key',
      maintenanceApiKeyMode: 'header',
    };

    render(<App />);

    expect(await screen.findByText(i18n.t('app.auth.runtimeBadge'))).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: i18n.t('app.auth.setApiKey') })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: i18n.t('app.auth.openSetup') })).toBeInTheDocument();
  });

  it('switches dashboard visuals into lite mode for Edge', async () => {
    const originalUserAgent = window.navigator.userAgent;
    window.history.pushState({}, '', '/memory');

    Object.defineProperty(window.navigator, 'userAgent', {
      configurable: true,
      value:
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0',
    });

    try {
      const { container } = render(<App />);

      expect(await screen.findByTestId('fluid-background-static')).toBeInTheDocument();
      expect(container.firstChild).toHaveAttribute('data-browser-performance', 'lite');
      await waitFor(() => {
        expect(document.documentElement.dataset.browserProfile).toBe('edge');
      });
    } finally {
      Object.defineProperty(window.navigator, 'userAgent', {
        configurable: true,
        value: originalUserAgent,
      });
    }
  });

  it('toggles language and persists the selection across remounts', async () => {
    const user = userEvent.setup();
    window.history.pushState({}, '', '/memory');

    const firstRender = render(<App />);

    expect(await screen.findByRole('button', { name: 'Set API key' })).toBeInTheDocument();
    await user.click(screen.getByTestId('language-toggle'));

    expect(await screen.findByRole('button', { name: '设置 API 密钥' })).toBeInTheDocument();
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe('zh-CN');

    firstRender.unmount();

    render(<App />);

    expect(await screen.findByRole('button', { name: '设置 API 密钥' })).toBeInTheDocument();
  });

  it('auto-opens setup assistant on first load when no auth is configured', async () => {
    window.localStorage.removeItem('memory-palace.setupAssistantDismissed');
    window.history.pushState({}, '', '/memory');

    render(<App />);

    expect(await screen.findByRole('dialog', { name: i18n.t('setup.title') })).toBeInTheDocument();
  });

  it('does not auto-open setup assistant when runtime auth is already present', async () => {
    window.localStorage.removeItem('memory-palace.setupAssistantDismissed');
    window.history.pushState({}, '', '/memory');
    window.__MEMORY_PALACE_RUNTIME__ = {
      maintenanceApiKey: 'runtime-key',
      maintenanceApiKeyMode: 'header',
    };

    render(<App />);

    expect(await screen.findByText(i18n.t('app.auth.runtimeBadge'))).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: i18n.t('setup.title') })).not.toBeInTheDocument();
    });
  });

  it('allows switching language from inside the setup assistant on first load', async () => {
    const user = userEvent.setup();
    window.localStorage.removeItem('memory-palace.setupAssistantDismissed');
    window.history.pushState({}, '', '/memory');

    render(<App />);

    const dialog = await screen.findByRole('dialog', { name: i18n.t('setup.title') });
    expect(within(dialog).getByText('Configure Memory Palace')).toBeInTheDocument();

    await user.click(within(dialog).getByTestId('setup-language-toggle'));

    expect(await screen.findByRole('dialog', { name: '配置 Memory Palace' })).toBeInTheDocument();
    const translatedDialog = screen.getByRole('dialog', { name: '配置 Memory Palace' });
    expect(within(translatedDialog).getByText('首启配置')).toBeInTheDocument();
    expect(
      within(translatedDialog).getByRole('button', { name: '档位 B · 仅 hash' })
    ).toBeInTheDocument();
    expect(
      within(translatedDialog).queryByRole('button', { name: /^(Profile B|Profile C|Profile D)\b/ })
    ).not.toBeInTheDocument();
  });

  it('keeps typed setup values when switching language inside the setup assistant', async () => {
    const user = userEvent.setup();
    window.localStorage.removeItem('memory-palace.setupAssistantDismissed');
    window.history.pushState({}, '', '/memory');

    render(<App />);

    const dialog = await screen.findByRole('dialog', { name: i18n.t('setup.title') });
    const apiKeyInput = within(dialog).getByPlaceholderText(i18n.t('setup.dashboard.apiKeyPlaceholder'));

    await user.type(apiKeyInput, 'typed-key-123');
    await user.click(within(dialog).getByTestId('setup-language-toggle'));

    const translatedDialog = await screen.findByRole('dialog', { name: '配置 Memory Palace' });
    expect(within(translatedDialog).getByDisplayValue('typed-key-123')).toBeInTheDocument();
  });

  it('relocalizes setup assistant status errors when switching language', async () => {
    const user = userEvent.setup();
    window.localStorage.removeItem('memory-palace.setupAssistantDismissed');
    window.history.pushState({}, '', '/memory');
    setupApi.getSetupStatus.mockRejectedValueOnce({
      message: 'Request failed with status code 500',
    });

    render(<App />);

    const dialog = await screen.findByRole('dialog', { name: i18n.t('setup.title') });
    expect(await within(dialog).findByText('Request failed with status code 500')).toBeInTheDocument();

    await user.click(within(dialog).getByTestId('setup-language-toggle'));

    const translatedDialog = await screen.findByRole('dialog', { name: '配置 Memory Palace' });
    expect(await within(translatedDialog).findByText('请求失败（状态码 500）')).toBeInTheDocument();
  });

  it('maps setup profile presets to the documented B/C/D retrieval shapes', async () => {
    const user = userEvent.setup();
    window.localStorage.removeItem('memory-palace.setupAssistantDismissed');
    window.history.pushState({}, '', '/memory');

    render(<App />);

    const dialog = await screen.findByRole('dialog', { name: i18n.t('setup.title') });
    const embeddingBackend = within(dialog).getByRole('combobox');
    const rerankerToggle = within(dialog).getByRole('checkbox', {
      name: new RegExp(`^${i18n.t('setup.retrieval.rerankerEnabledLabel')}`),
    });

    await user.click(within(dialog).getByRole('button', { name: i18n.t('setup.retrieval.presets.b') }));
    expect(embeddingBackend).toHaveValue('hash');
    expect(rerankerToggle).not.toBeChecked();
    expect(within(dialog).queryByPlaceholderText(i18n.t('setup.retrieval.routerApiBasePlaceholder'))).not.toBeInTheDocument();

    await user.click(within(dialog).getByRole('button', { name: i18n.t('setup.retrieval.presets.c') }));
    expect(embeddingBackend).toHaveValue('router');
    expect(rerankerToggle).toBeChecked();
    expect(within(dialog).getByPlaceholderText(i18n.t('setup.retrieval.routerApiBasePlaceholder'))).toBeInTheDocument();
    expect(within(dialog).queryByPlaceholderText(i18n.t('setup.retrieval.embeddingApiBasePlaceholder'))).not.toBeInTheDocument();
    expect(within(dialog).queryByPlaceholderText(i18n.t('setup.retrieval.rerankerApiBasePlaceholder'))).not.toBeInTheDocument();

    await user.click(within(dialog).getByRole('button', { name: i18n.t('setup.retrieval.presets.d') }));
    expect(embeddingBackend).toHaveValue('router');
    expect(rerankerToggle).toBeChecked();
    expect(within(dialog).getByPlaceholderText(i18n.t('setup.retrieval.routerApiBasePlaceholder'))).toBeInTheDocument();
  });

  it('does not embed the raw api key in the routes key', () => {
    const routesKey = buildRoutesKey(
      {
        source: 'stored',
        mode: 'header',
        key: 'super-secret-key',
      },
      3
    );

    expect(routesKey).toBe('stored:header:3');
    expect(routesKey).not.toContain('super-secret-key');
    expect(buildRoutesKey(null, 4)).toBe('no-auth:4');
  });
});
