import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import RootErrorBoundary from './RootErrorBoundary';

function ThrowOnRender() {
  throw new Error('render boom');
}

describe('RootErrorBoundary', () => {
  it('shows a fallback shell when the child tree crashes during render', () => {
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
});
