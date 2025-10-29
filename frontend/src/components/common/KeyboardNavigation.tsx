import React, { useEffect, useRef } from 'react';

interface KeyboardNavigationProps {
  children: React.ReactNode;
  trapFocus?: boolean;
  autoFocus?: boolean;
  onEscape?: () => void;
}

export const KeyboardNavigation: React.FC<KeyboardNavigationProps> = ({
  children,
  trapFocus = false,
  autoFocus = false,
  onEscape,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const firstFocusableRef = useRef<HTMLElement | null>(null);
  const lastFocusableRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const focusableElements = containerRef.current.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    ) as NodeListOf<HTMLElement>;

    if (focusableElements.length > 0) {
      firstFocusableRef.current = focusableElements[0];
      lastFocusableRef.current = focusableElements[focusableElements.length - 1];

      if (autoFocus) {
        firstFocusableRef.current.focus();
      }
    }
  }, [autoFocus]);

  useEffect(() => {
    if (!trapFocus) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && onEscape) {
        onEscape();
        return;
      }

      if (event.key === 'Tab') {
        if (event.shiftKey) {
          // Shift + Tab
          if (document.activeElement === firstFocusableRef.current) {
            event.preventDefault();
            lastFocusableRef.current?.focus();
          }
        } else {
          // Tab
          if (document.activeElement === lastFocusableRef.current) {
            event.preventDefault();
            firstFocusableRef.current?.focus();
          }
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [trapFocus, onEscape]);

  return (
    <div ref={containerRef} className="keyboard-navigation">
      {children}
    </div>
  );
};

// Hook for managing keyboard shortcuts
export const useKeyboardShortcuts = (shortcuts: Record<string, () => void>) => {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const key = event.key.toLowerCase();
      const modifiers = {
        ctrl: event.ctrlKey,
        alt: event.altKey,
        shift: event.shiftKey,
        meta: event.metaKey,
      };

      // Create shortcut string (e.g., "ctrl+k", "alt+shift+n")
      const shortcutParts = [];
      if (modifiers.ctrl) shortcutParts.push('ctrl');
      if (modifiers.alt) shortcutParts.push('alt');
      if (modifiers.shift) shortcutParts.push('shift');
      if (modifiers.meta) shortcutParts.push('meta');
      shortcutParts.push(key);
      
      const shortcutString = shortcutParts.join('+');

      if (shortcuts[shortcutString]) {
        event.preventDefault();
        shortcuts[shortcutString]();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [shortcuts]);
};

// Hook for managing focus
export const useFocusManagement = () => {
  const focusRef = useRef<HTMLElement | null>(null);

  const setFocus = (element: HTMLElement | null) => {
    focusRef.current = element;
    element?.focus();
  };

  const restoreFocus = () => {
    focusRef.current?.focus();
  };

  const moveFocusToNext = () => {
    const focusableElements = document.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    ) as NodeListOf<HTMLElement>;

    const currentIndex = Array.from(focusableElements).indexOf(document.activeElement as HTMLElement);
    const nextIndex = (currentIndex + 1) % focusableElements.length;
    focusableElements[nextIndex]?.focus();
  };

  const moveFocusToPrevious = () => {
    const focusableElements = document.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    ) as NodeListOf<HTMLElement>;

    const currentIndex = Array.from(focusableElements).indexOf(document.activeElement as HTMLElement);
    const previousIndex = currentIndex === 0 ? focusableElements.length - 1 : currentIndex - 1;
    focusableElements[previousIndex]?.focus();
  };

  return {
    setFocus,
    restoreFocus,
    moveFocusToNext,
    moveFocusToPrevious,
  };
};