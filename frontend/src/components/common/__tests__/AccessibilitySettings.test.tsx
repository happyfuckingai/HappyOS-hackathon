import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { axe, toHaveNoViolations } from 'jest-axe';
import { AccessibilitySettings } from '../AccessibilitySettings';
import { AccessibilityProvider } from '../AccessibilityProvider';

// Extend Jest matchers
expect.extend(toHaveNoViolations);

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

const renderWithProvider = (isOpen: boolean = true, onClose = jest.fn()) => {
  return render(
    <AccessibilityProvider>
      <AccessibilitySettings isOpen={isOpen} onClose={onClose} />
    </AccessibilityProvider>
  );
};

describe('AccessibilitySettings', () => {
  beforeEach(() => {
    localStorageMock.getItem.mockClear();
    localStorageMock.setItem.mockClear();
  });

  it('renders when isOpen is true', () => {
    renderWithProvider(true);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Accessibility Settings')).toBeInTheDocument();
  });

  it('does not render when isOpen is false', () => {
    renderWithProvider(false);

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('has proper dialog attributes', () => {
    renderWithProvider();

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-labelledby', 'accessibility-settings-title');
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = jest.fn();
    renderWithProvider(true, onClose);

    const closeButton = screen.getByRole('button', { name: /close accessibility settings/i });
    fireEvent.click(closeButton);

    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when save button is clicked', () => {
    const onClose = jest.fn();
    renderWithProvider(true, onClose);

    const saveButton = screen.getByRole('button', { name: /save settings/i });
    fireEvent.click(saveButton);

    expect(onClose).toHaveBeenCalled();
  });

  it('displays font size options with proper radio group', () => {
    renderWithProvider();

    const radioGroup = screen.getByRole('radiogroup');
    expect(radioGroup).toBeInTheDocument();

    const smallOption = screen.getByRole('radio', { name: /set font size to small/i });
    const mediumOption = screen.getByRole('radio', { name: /set font size to medium/i });
    const largeOption = screen.getByRole('radio', { name: /set font size to large/i });

    expect(smallOption).toBeInTheDocument();
    expect(mediumOption).toBeInTheDocument();
    expect(largeOption).toBeInTheDocument();

    // Medium should be selected by default
    expect(mediumOption).toHaveAttribute('aria-checked', 'true');
  });

  it('changes font size when option is clicked', () => {
    renderWithProvider();

    const largeOption = screen.getByRole('radio', { name: /set font size to large/i });
    fireEvent.click(largeOption);

    expect(largeOption).toHaveAttribute('aria-checked', 'true');
    expect(localStorageMock.setItem).toHaveBeenCalledWith('accessibility-font-size', 'large');
  });

  it('displays high contrast toggle with proper switch attributes', () => {
    renderWithProvider();

    const toggle = screen.getByRole('switch', { name: /enable high contrast mode/i });
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute('aria-checked', 'false');
  });

  it('toggles high contrast mode when switch is clicked', () => {
    renderWithProvider();

    const toggle = screen.getByRole('switch', { name: /enable high contrast mode/i });
    fireEvent.click(toggle);

    expect(toggle).toHaveAttribute('aria-checked', 'true');
    expect(localStorageMock.setItem).toHaveBeenCalledWith('accessibility-high-contrast', 'true');
  });

  it('displays keyboard shortcuts information', () => {
    renderWithProvider();

    expect(screen.getByText('Keyboard Shortcuts')).toBeInTheDocument();
    expect(screen.getByText('Toggle microphone:')).toBeInTheDocument();
    expect(screen.getByText('Toggle camera:')).toBeInTheDocument();
    expect(screen.getByText('Open settings:')).toBeInTheDocument();
    expect(screen.getByText('Leave meeting:')).toBeInTheDocument();

    // Check for keyboard shortcut indicators
    expect(screen.getByText('M')).toBeInTheDocument();
    expect(screen.getByText('V')).toBeInTheDocument();
    expect(screen.getByText('S')).toBeInTheDocument();
    expect(screen.getByText('Esc')).toBeInTheDocument();
  });

  it('has no accessibility violations', async () => {
    const { container } = renderWithProvider();
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('properly labels form controls', () => {
    renderWithProvider();

    // Font size radio group should have proper labeling
    const radioGroup = screen.getByRole('radiogroup');
    expect(radioGroup).toHaveAttribute('aria-labelledby');

    // High contrast toggle should have proper labeling
    const toggle = screen.getByRole('switch');
    expect(toggle).toHaveAttribute('aria-label');
  });

  it('provides descriptive text for settings', () => {
    renderWithProvider();

    expect(screen.getByText('Increases contrast for better visibility')).toBeInTheDocument();
  });

  it('handles keyboard navigation properly', () => {
    renderWithProvider();

    const dialog = screen.getByRole('dialog');
    
    // Should be able to tab through interactive elements
    const interactiveElements = dialog.querySelectorAll(
      'button, [role="radio"], [role="switch"]'
    );
    
    expect(interactiveElements.length).toBeGreaterThan(0);
    
    // Each interactive element should be focusable
    interactiveElements.forEach(element => {
      expect(element).not.toHaveAttribute('tabindex', '-1');
    });
  });
});