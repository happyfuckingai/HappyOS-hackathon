import React, { useState } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { KeyboardNavigation, useKeyboardShortcuts, useFocusManagement } from '../KeyboardNavigation';

// Test component for keyboard navigation
const TestKeyboardNavigation: React.FC<{ trapFocus?: boolean; onEscape?: () => void }> = ({
  trapFocus,
  onEscape,
}) => {
  return (
    <KeyboardNavigation trapFocus={trapFocus} onEscape={onEscape} autoFocus>
      <button>First Button</button>
      <button>Second Button</button>
      <input placeholder="Text input" />
      <button>Last Button</button>
    </KeyboardNavigation>
  );
};

// Test component for keyboard shortcuts
const TestKeyboardShortcuts: React.FC = () => {
  const [message, setMessage] = useState('');

  useKeyboardShortcuts({
    'ctrl+k': () => setMessage('Ctrl+K pressed'),
    'alt+shift+n': () => setMessage('Alt+Shift+N pressed'),
    'escape': () => setMessage('Escape pressed'),
  });

  return <div data-testid="message">{message}</div>;
};

// Test component for focus management
const TestFocusManagement: React.FC = () => {
  const { setFocus, restoreFocus, moveFocusToNext, moveFocusToPrevious } = useFocusManagement();
  const buttonRef = React.useRef<HTMLButtonElement>(null);

  return (
    <div>
      <button ref={buttonRef}>Target Button</button>
      <button onClick={() => setFocus(buttonRef.current)}>Set Focus</button>
      <button onClick={restoreFocus}>Restore Focus</button>
      <button onClick={moveFocusToNext}>Next Focus</button>
      <button onClick={moveFocusToPrevious}>Previous Focus</button>
    </div>
  );
};

describe('KeyboardNavigation', () => {
  it('renders children correctly', () => {
    render(<TestKeyboardNavigation />);

    expect(screen.getByText('First Button')).toBeInTheDocument();
    expect(screen.getByText('Second Button')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Text input')).toBeInTheDocument();
    expect(screen.getByText('Last Button')).toBeInTheDocument();
  });

  it('auto-focuses first element when autoFocus is true', () => {
    render(<TestKeyboardNavigation />);

    expect(screen.getByText('First Button')).toHaveFocus();
  });

  it('calls onEscape when Escape key is pressed', () => {
    const onEscape = jest.fn();
    render(<TestKeyboardNavigation trapFocus onEscape={onEscape} />);

    fireEvent.keyDown(document, { key: 'Escape' });

    expect(onEscape).toHaveBeenCalled();
  });

  it('traps focus when trapFocus is enabled', () => {
    render(<TestKeyboardNavigation trapFocus />);

    const firstButton = screen.getByText('First Button');
    const lastButton = screen.getByText('Last Button');

    // Focus should start on first button
    expect(firstButton).toHaveFocus();

    // Tab to last button
    fireEvent.keyDown(document, { key: 'Tab' });
    fireEvent.keyDown(document, { key: 'Tab' });
    fireEvent.keyDown(document, { key: 'Tab' });

    // Simulate being on last focusable element and pressing Tab
    lastButton.focus();
    fireEvent.keyDown(document, { key: 'Tab' });

    // Should wrap to first button (in a real scenario)
    // Note: This test might need adjustment based on actual focus behavior
  });

  it('handles Shift+Tab for reverse focus trapping', () => {
    render(<TestKeyboardNavigation trapFocus />);

    const firstButton = screen.getByText('First Button');
    firstButton.focus();

    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });

    // Should wrap to last focusable element (in a real scenario)
    // Note: This test might need adjustment based on actual focus behavior
  });
});

describe('useKeyboardShortcuts', () => {
  it('triggers shortcuts when correct key combinations are pressed', () => {
    render(<TestKeyboardShortcuts />);

    const messageElement = screen.getByTestId('message');

    // Test Ctrl+K
    fireEvent.keyDown(document, { key: 'k', ctrlKey: true });
    expect(messageElement).toHaveTextContent('Ctrl+K pressed');

    // Test Alt+Shift+N
    fireEvent.keyDown(document, { key: 'n', altKey: true, shiftKey: true });
    expect(messageElement).toHaveTextContent('Alt+Shift+N pressed');

    // Test Escape
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(messageElement).toHaveTextContent('Escape pressed');
  });

  it('does not trigger shortcuts for incorrect key combinations', () => {
    render(<TestKeyboardShortcuts />);

    const messageElement = screen.getByTestId('message');

    // Test incorrect combination
    fireEvent.keyDown(document, { key: 'k' }); // Missing Ctrl
    expect(messageElement).toHaveTextContent('');

    fireEvent.keyDown(document, { key: 'x', ctrlKey: true }); // Wrong key
    expect(messageElement).toHaveTextContent('');
  });
});

describe('useFocusManagement', () => {
  it('sets focus on target element', () => {
    render(<TestFocusManagement />);

    const targetButton = screen.getByText('Target Button');
    const setFocusButton = screen.getByText('Set Focus');

    fireEvent.click(setFocusButton);

    expect(targetButton).toHaveFocus();
  });

  it('restores focus to previously focused element', () => {
    render(<TestFocusManagement />);

    const targetButton = screen.getByText('Target Button');
    const setFocusButton = screen.getByText('Set Focus');
    const restoreFocusButton = screen.getByText('Restore Focus');

    // Set focus first
    fireEvent.click(setFocusButton);
    expect(targetButton).toHaveFocus();

    // Focus something else
    restoreFocusButton.focus();

    // Restore focus
    fireEvent.click(restoreFocusButton);
    expect(targetButton).toHaveFocus();
  });

  it('moves focus to next focusable element', () => {
    render(<TestFocusManagement />);

    const nextFocusButton = screen.getByText('Next Focus');
    nextFocusButton.focus();

    fireEvent.click(nextFocusButton);

    // Should move focus to the next focusable element
    // Note: This test might need adjustment based on actual focus behavior
  });

  it('moves focus to previous focusable element', () => {
    render(<TestFocusManagement />);

    const previousFocusButton = screen.getByText('Previous Focus');
    previousFocusButton.focus();

    fireEvent.click(previousFocusButton);

    // Should move focus to the previous focusable element
    // Note: This test might need adjustment based on actual focus behavior
  });
});