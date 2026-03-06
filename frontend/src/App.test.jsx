import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

import App from './App';

vi.mock('./features/memory/MemoryBrowser', () => ({
  default: () => <div>memory-page</div>,
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
  afterEach(() => {
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
});
