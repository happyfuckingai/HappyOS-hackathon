import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BrowserRouter } from 'react-router-dom';
import AppShell from '../AppShell';
import { TenantProvider } from '../../../contexts/TenantContext';

// Mock Header component
jest.mock('../Header', () => {
  return function MockHeader() {
    return <header data-testid="header">Header</header>;
  };
});

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      <TenantProvider>
        {component}
      </TenantProvider>
    </BrowserRouter>
  );
};

describe('AppShell', () => {
  it('renders children correctly', () => {
    renderWithRouter(
      <AppShell>
        <div data-testid="test-content">Test Content</div>
      </AppShell>
    );

    expect(screen.getByTestId('test-content')).toBeInTheDocument();
    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('renders header component', () => {
    renderWithRouter(
      <AppShell>
        <div>Content</div>
      </AppShell>
    );

    expect(screen.getByTestId('header')).toBeInTheDocument();
  });

  it('has correct layout structure', () => {
    const { container } = renderWithRouter(
      <AppShell>
        <div>Content</div>
      </AppShell>
    );

    const appShell = container.firstChild as HTMLElement;
    expect(appShell).toHaveClass('min-h-screen', 'flex', 'flex-col', 'bg-aurora-wash');

    const main = appShell.querySelector('main');
    expect(main).toHaveClass('flex-1', 'relative');
  });

  it('applies correct styling classes', () => {
    const { container } = renderWithRouter(
      <AppShell>
        <div>Content</div>
      </AppShell>
    );

    const backgroundDiv = container.querySelector('.bg-radial-spark');
    expect(backgroundDiv).toBeInTheDocument();
    expect(backgroundDiv).toHaveClass('absolute', 'inset-0', 'pointer-events-none');

    const contentWrapper = container.querySelector('.relative.z-10');
    expect(contentWrapper).toBeInTheDocument();
  });

  it('renders multiple children correctly', () => {
    renderWithRouter(
      <AppShell>
        <div data-testid="child-1">Child 1</div>
        <div data-testid="child-2">Child 2</div>
      </AppShell>
    );

    expect(screen.getByTestId('child-1')).toBeInTheDocument();
    expect(screen.getByTestId('child-2')).toBeInTheDocument();
  });
});