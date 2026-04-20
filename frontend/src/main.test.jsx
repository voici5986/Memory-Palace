import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const renderSpy = vi.fn();
const createRootSpy = vi.fn(() => ({ render: renderSpy }));
const primeDocumentLanguageFromBootstrap = vi.fn();
let addEventListenerSpy;
let consoleErrorSpy;

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
    addEventListenerSpy = vi.spyOn(window, 'addEventListener');
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    delete window.__memory_palace_unhandled_rejection_handler__;
  });

  afterEach(() => {
    vi.resetModules();
    document.body.innerHTML = '';
    consoleErrorSpy.mockRestore();
  });

  it('wraps the root app with a global error boundary', async () => {
    await import('./main.jsx');

    expect(createRootSpy).toHaveBeenCalledWith(document.getElementById('root'));
    expect(renderSpy).toHaveBeenCalledTimes(1);
    expect(primeDocumentLanguageFromBootstrap).toHaveBeenCalledTimes(1);

    const rootElement = renderSpy.mock.calls[0][0];
    expect(rootElement.type).toBe(React.StrictMode);
    expect(rootElement.props.children.type.name).toBe('RootErrorBoundary');
  });

  it('registers an unhandled rejection handler that logs without replacing the app shell', async () => {
    const { registerGlobalUnhandledRejectionHandler } = await import('./main.jsx');

    const registration = addEventListenerSpy.mock.calls.find(
      ([eventName]) => eventName === 'unhandledrejection'
    );
    expect(registration).toBeDefined();
    expect(registration?.[1]).toEqual(expect.any(Function));
    expect(registerGlobalUnhandledRejectionHandler(window)).toBe(registration?.[1]);

    const preventDefault = vi.fn();
    registration?.[1]({ preventDefault, reason: new Error('async boom') });

    expect(preventDefault).toHaveBeenCalledTimes(1);
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      'Unhandled promise rejection',
      expect.any(Error)
    );
    expect(renderSpy).toHaveBeenCalledTimes(1);
  });
});
