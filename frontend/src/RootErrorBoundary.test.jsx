import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

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
});
