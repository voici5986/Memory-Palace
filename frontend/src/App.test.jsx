import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@testing-library/react';

import App, { buildRoutesKey } from './App';
import i18n, { LOCALE_STORAGE_KEY } from './i18n';

const { memoryMountCounter } = vi.hoisted(() => ({
  memoryMountCounter: { current: 0 },
}));

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

vi.mock('./components/AgentationLite', () => ({
  default: () => null,
}));

describe('App routing', () => {
  beforeEach(async () => {
    memoryMountCounter.current = 0;
    window.localStorage?.removeItem?.('memory-palace.dashboardAuth');
    window.localStorage?.removeItem?.(LOCALE_STORAGE_KEY);
    delete window.__MEMORY_PALACE_RUNTIME__;
    await i18n.changeLanguage('en');
    window.localStorage?.removeItem?.(LOCALE_STORAGE_KEY);
    vi.spyOn(window, 'prompt').mockReturnValue(null);
    vi.spyOn(window, 'alert').mockImplementation(() => {});
  });

  afterEach(() => {
    window.history.pushState({}, '', '/');
    vi.restoreAllMocks();
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

  it('stores API key through header action when runtime config is absent', async () => {
    const user = userEvent.setup();
    window.history.pushState({}, '', '/memory');
    window.prompt.mockReturnValue('stored-key');

    render(<App />);

    await user.click(screen.getByRole('button', { name: i18n.t('app.auth.setApiKey') }));

    expect(window.localStorage.getItem('memory-palace.dashboardAuth')).toContain('stored-key');
    expect(await screen.findByRole('button', { name: i18n.t('app.auth.updateApiKey') })).toBeInTheDocument();
  });

  it('remounts routes after stored auth changes without depending on raw key text', async () => {
    const user = userEvent.setup();
    window.history.pushState({}, '', '/memory');
    window.prompt.mockReturnValue('stored-key');

    render(<App />);
    expect(await screen.findByText('memory-page')).toBeInTheDocument();
    await waitFor(() => expect(memoryMountCounter.current).toBe(1));

    await user.click(screen.getByRole('button', { name: i18n.t('app.auth.setApiKey') }));

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
