import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const renderSpy = vi.fn();
const createRootSpy = vi.fn(() => ({ render: renderSpy }));
const primeDocumentLanguageFromBootstrap = vi.fn();

vi.mock('react-dom/client', () => ({
  default: { createRoot: createRootSpy },
  createRoot: createRootSpy,
}));

vi.mock('./App.jsx', () => {
  function MockApp() {
    return <div>mock-app</div>;
  }

  return { default: MockApp };
});

vi.mock('./i18n', () => ({
  primeDocumentLanguageFromBootstrap,
}));

vi.mock('./index.css', () => ({}));

describe('main entrypoint', () => {
  beforeEach(() => {
    document.body.innerHTML = '<div id="root"></div>';
    renderSpy.mockReset();
    createRootSpy.mockClear();
    primeDocumentLanguageFromBootstrap.mockReset();
  });

  afterEach(() => {
    vi.resetModules();
    document.body.innerHTML = '';
  });

  it('wraps the root app with a global error boundary', async () => {
    await import('./main.jsx');

    expect(createRootSpy).toHaveBeenCalledWith(document.getElementById('root'));
    expect(renderSpy).toHaveBeenCalledTimes(1);

    const rootElement = renderSpy.mock.calls[0][0];
    expect(rootElement.type).toBe(React.StrictMode);
    expect(rootElement.props.children.type.name).toBe('RootErrorBoundary');
  });
});
