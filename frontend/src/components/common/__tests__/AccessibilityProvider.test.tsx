import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { AccessibilityProvider, useAccessibility } from '../AccessibilityProvider';

// Test component that uses the accessibility context
const TestComponent: React.FC = () => {
  const {
    isHighContrast,
    fontSize,
    toggleHighContrast,
    setFontSize,
    announceToScreenReader,
  } = useAccessibility();

  return (
    <div>
      <div data-testid="high-contrast">{isHighContrast.toString()}</div>
      <div data-testid="font-size">{fontSize}</div>
      <button onClick={toggleHighContrast}>Toggle High Contrast</button>
      <button onClick={() => setFontSize('large')}>Set Large Font</button>
      <button onClick={() => announceToScreenReader('Test announcement')}>
        Announce
      </button>
    </div>
  );
};

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

describe('AccessibilityProvider', () => {
  beforeEach(() => {
    localStorageMock.getItem.mockClear();
    localStorageMock.setItem.mockClear();
    document.documentElement.className = '';
  });

  it('provides default accessibility values', () => {
    render(
      <AccessibilityProvider>
        <TestComponent />
      </AccessibilityProvider>
    );

    expect(screen.getByTestId('high-contrast')).toHaveTextContent('false');
    expect(screen.getByTestId('font-size')).toHaveTextContent('medium');
  });

  it('toggles high contrast mode', () => {
    render(
      <AccessibilityProvider>
        <TestComponent />
      </AccessibilityProvider>
    );

    const toggleButton = screen.getByText('Toggle High Contrast');
    fireEvent.click(toggleButton);

    expect(screen.getByTestId('high-contrast')).toHaveTextContent('true');
    expect(localStorageMock.setItem).toHaveBeenCalledWith('accessibility-high-contrast', 'true');
  });

  it('changes font size', () => {
    render(
      <AccessibilityProvider>
        <TestComponent />
      </AccessibilityProvider>
    );

    const fontButton = screen.getByText('Set Large Font');
    fireEvent.click(fontButton);

    expect(screen.getByTestId('font-size')).toHaveTextContent('large');
    expect(localStorageMock.setItem).toHaveBeenCalledWith('accessibility-font-size', 'large');
  });

  it('applies CSS classes to document element', () => {
    render(
      <AccessibilityProvider>
        <TestComponent />
      </AccessibilityProvider>
    );

    const toggleButton = screen.getByText('Toggle High Contrast');
    fireEvent.click(toggleButton);

    expect(document.documentElement.classList.contains('high-contrast')).toBe(true);
    expect(document.documentElement.classList.contains('font-medium')).toBe(true);
  });

  it('loads saved preferences from localStorage', () => {
    localStorageMock.getItem.mockImplementation((key) => {
      if (key === 'accessibility-font-size') return 'large';
      if (key === 'accessibility-high-contrast') return 'true';
      return null;
    });

    render(
      <AccessibilityProvider>
        <TestComponent />
      </AccessibilityProvider>
    );

    expect(screen.getByTestId('font-size')).toHaveTextContent('large');
    expect(screen.getByTestId('high-contrast')).toHaveTextContent('true');
  });

  it('creates screen reader announcements', () => {
    render(
      <AccessibilityProvider>
        <TestComponent />
      </AccessibilityProvider>
    );

    const announceButton = screen.getByText('Announce');
    
    act(() => {
      fireEvent.click(announceButton);
    });

    // Check that an element with aria-live was created
    const announcements = document.querySelectorAll('[aria-live="polite"]');
    expect(announcements.length).toBeGreaterThan(0);
  });

  it('respects user preferences for reduced motion', () => {
    // Mock prefers-reduced-motion
    window.matchMedia = jest.fn().mockImplementation(query => ({
      matches: query === '(prefers-reduced-motion: reduce)',
      media: query,
      onchange: null,
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    }));

    render(
      <AccessibilityProvider>
        <TestComponent />
      </AccessibilityProvider>
    );

    expect(document.documentElement.classList.contains('reduced-motion')).toBe(true);
  });

  it('throws error when used outside provider', () => {
    // Suppress console.error for this test
    const originalError = console.error;
    console.error = jest.fn();

    expect(() => {
      render(<TestComponent />);
    }).toThrow('useAccessibility must be used within an AccessibilityProvider');

    console.error = originalError;
  });
});