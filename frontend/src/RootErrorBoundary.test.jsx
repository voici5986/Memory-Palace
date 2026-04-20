import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import RootErrorBoundary from './RootErrorBoundary';
import i18n from './i18n';

function ThrowOnRender() {
  throw new Error('render boom');
}

describe('RootErrorBoundary', () => {
  it('shows a fallback shell when the child tree crashes during render', () => {
    void i18n.changeLanguage('en');
    render(
      <RootErrorBoundary>
        <ThrowOnRender />
      </RootErrorBoundary>
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Something went wrong.' })
    ).toBeInTheDocument();
    expect(
      screen.getByText('Please refresh the page and try again.')
    ).toBeInTheDocument();
  });

  it('uses the active locale for fallback copy', async () => {
    await i18n.changeLanguage('zh-CN');

    render(
      <RootErrorBoundary>
        <ThrowOnRender />
      </RootErrorBoundary>
    );

    expect(
      screen.getByRole('heading', { name: '页面发生错误。' })
    ).toBeInTheDocument();
    expect(screen.getByText('请刷新页面后重试。')).toBeInTheDocument();

    await i18n.changeLanguage('en');
  });

  it('offers a refresh action from the fallback shell', () => {
    const reload = vi.fn();
    const originalLocation = window.location;
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...originalLocation, reload },
    });

    try {
      void i18n.changeLanguage('en');
      render(
        <RootErrorBoundary>
          <ThrowOnRender />
        </RootErrorBoundary>
      );

      fireEvent.click(screen.getByRole('button', { name: i18n.t('common.actions.refresh') }));
      expect(reload).toHaveBeenCalledTimes(1);
    } finally {
      Object.defineProperty(window, 'location', {
        configurable: true,
        value: originalLocation,
      });
    }
  });

  it('reports render crashes through componentDidCatch', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    try {
      void i18n.changeLanguage('en');
      render(
        <RootErrorBoundary>
          <ThrowOnRender />
        </RootErrorBoundary>
      );

      expect(consoleSpy).toHaveBeenCalledWith(
        'RootErrorBoundary caught render error',
        expect.any(Error),
        expect.objectContaining({
          componentStack: expect.any(String),
        })
      );
    } finally {
      consoleSpy.mockRestore();
    }
  });
});
