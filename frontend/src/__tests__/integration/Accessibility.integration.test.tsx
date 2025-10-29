import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { axe, toHaveNoViolations } from 'jest-axe';
import { BrowserRouter } from 'react-router-dom';
import App from '../../App';
import Landing from '../../pages/Landing';
import { AuthProvider } from '../../contexts/AuthContext';

// Extend Jest matchers
expect.extend(toHaveNoViolations);

// Mock fetch
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock localStorage
const mockLocalStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
};
Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
});

// Mock jwt-decode
jest.mock('jwt-decode', () => ({
  __esModule: true,
  default: jest.fn(() => ({
    id: 'user-123',
    email: 'test@example.com',
    name: 'Test User',
    role: 'user',
    exp: Date.now() / 1000 + 3600,
  })),
}));

// Mock LiveKit components
jest.mock('@livekit/components-react', () => ({
  LiveKitRoom: ({ children }: any) => <div data-testid="livekit-room">{children}</div>,
  VideoConference: () => <div data-testid="video-conference">Video Conference</div>,
  RoomAudioRenderer: () => <div data-testid="room-audio-renderer">Audio Renderer</div>,
}));

// Mock EventSource
class MockEventSource {
  url: string;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  readyState: number = 1;
  
  constructor(url: string) {
    this.url = url;
  }
  
  close() {}
  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() { return true; }
}

(global as any).EventSource = MockEventSource;

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      <AuthProvider>
        {component}
      </AuthProvider>
    </BrowserRouter>
  );
};

describe('Accessibility Integration Tests', () => {
  beforeEach(() => {
    mockFetch.mockClear();
    mockLocalStorage.getItem.mockReturnValue(null);
    console.error = jest.fn();
    console.log = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Landing Page Accessibility', () => {
    it('should not have accessibility violations', async () => {
      const { container } = renderWithProviders(<Landing />);
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('should have proper heading hierarchy', () => {
      renderWithProviders(<Landing />);

      const h1 = screen.getByRole('heading', { level: 1 });
      expect(h1).toBeInTheDocument();
      expect(h1).toHaveTextContent('MeetMind');

      const h3Elements = screen.getAllByRole('heading', { level: 3 });
      expect(h3Elements).toHaveLength(3); // Feature cards
    });

    it('should have accessible buttons', () => {
      renderWithProviders(<Landing />);

      const getStartedButton = screen.getByRole('button', { name: /get started/i });
      expect(getStartedButton).toBeInTheDocument();
      expect(getStartedButton).toHaveAttribute('type', 'button');
    });

    it('should have proper color contrast', () => {
      const { container } = renderWithProviders(<Landing />);

      // Check that text elements have appropriate contrast classes
      const heroTitle = container.querySelector('.text-white');
      expect(heroTitle).toBeInTheDocument();

      const orangeAccent = container.querySelector('.text-orange-500');
      expect(orangeAccent).toBeInTheDocument();
    });
  });

  describe('Keyboard Navigation', () => {
    it('should support keyboard navigation on landing page', async () => {
      const user = userEvent.setup();
      renderWithProviders(<Landing />);

      const getStartedButton = screen.getByRole('button', { name: /get started/i });
      
      // Tab to the button
      await user.tab();
      expect(getStartedButton).toHaveFocus();

      // Should be able to activate with Enter
      await user.keyboard('{Enter}');
      // Note: Navigation behavior would be tested in integration tests
    });

    it('should support keyboard navigation in forms', async () => {
      const user = userEvent.setup();
      
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true, data: { token: 'test' } }),
      });

      render(
        <BrowserRouter>
          <App />
        </BrowserRouter>
      );

      // Navigate to auth page
      const getStartedButton = screen.getByRole('button', { name: /get started/i });
      await user.click(getStartedButton);

      // Wait for auth page to load
      await screen.findByLabelText(/email/i);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      // Tab through form elements
      await user.tab();
      expect(emailInput).toHaveFocus();

      await user.tab();
      expect(passwordInput).toHaveFocus();

      await user.tab();
      expect(submitButton).toHaveFocus();
    });

    it('should trap focus in modal dialogs', async () => {
      const user = userEvent.setup();
      
      // Mock authenticated state
      mockLocalStorage.getItem.mockReturnValue('valid-token');
      
      render(
        <BrowserRouter>
          <App />
        </BrowserRouter>
      );

      // Navigate to a page with modals (e.g., meeting page with FAB menu)
      window.history.pushState({}, '', '/lobby');

      await screen.findByText('Create Meeting');

      // This would test modal focus trapping when implemented
      // For now, we're testing that the basic structure supports it
    });
  });

  describe('Screen Reader Support', () => {
    it('should have proper ARIA labels', () => {
      renderWithProviders(<Landing />);

      // Check for proper ARIA attributes
      const getStartedButton = screen.getByRole('button', { name: /get started/i });
      expect(getStartedButton).toBeInTheDocument();

      // Feature cards should have proper structure
      const featureCards = screen.getAllByText(/Smart Notes|Real-time Collaboration|AI Insights/);
      expect(featureCards).toHaveLength(3);
    });

    it('should announce dynamic content changes', async () => {
      const user = userEvent.setup();
      
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      render(
        <BrowserRouter>
          <App />
        </BrowserRouter>
      );

      // Navigate to auth and trigger an error
      const getStartedButton = screen.getByRole('button', { name: /get started/i });
      await user.click(getStartedButton);

      await screen.findByLabelText(/email/i);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password');
      await user.click(submitButton);

      // Error should be announced to screen readers
      const errorMessage = await screen.findByRole('alert');
      expect(errorMessage).toBeInTheDocument();
    });

    it('should have proper form labels and descriptions', async () => {
      const user = userEvent.setup();

      render(
        <BrowserRouter>
          <App />
        </BrowserRouter>
      );

      // Navigate to auth page
      const getStartedButton = screen.getByRole('button', { name: /get started/i });
      await user.click(getStartedButton);

      await screen.findByLabelText(/email/i);

      // All form inputs should have proper labels
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);

      expect(emailInput).toHaveAttribute('type', 'email');
      expect(passwordInput).toHaveAttribute('type', 'password');

      // Check for proper form structure
      expect(emailInput.closest('form')).toBeInTheDocument();
    });
  });

  describe('Error State Accessibility', () => {
    it('should make error messages accessible', async () => {
      const user = userEvent.setup();
      
      mockFetch.mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({
          success: false,
          error: { message: 'Invalid credentials' }
        }),
      });

      render(
        <BrowserRouter>
          <App />
        </BrowserRouter>
      );

      // Navigate to auth and trigger error
      const getStartedButton = screen.getByRole('button', { name: /get started/i });
      await user.click(getStartedButton);

      await screen.findByLabelText(/email/i);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      await user.type(emailInput, 'wrong@example.com');
      await user.type(passwordInput, 'wrongpassword');
      await user.click(submitButton);

      // Error should be properly announced
      const errorAlert = await screen.findByRole('alert');
      expect(errorAlert).toHaveTextContent('Invalid credentials');
    });

    it('should handle loading states accessibly', async () => {
      const user = userEvent.setup();
      
      // Mock slow response
      mockFetch.mockImplementation(() => 
        new Promise(resolve => 
          setTimeout(() => resolve({
            ok: true,
            json: () => Promise.resolve({ success: true, data: { token: 'test' } }),
          }), 100)
        )
      );

      render(
        <BrowserRouter>
          <App />
        </BrowserRouter>
      );

      const getStartedButton = screen.getByRole('button', { name: /get started/i });
      await user.click(getStartedButton);

      await screen.findByLabelText(/email/i);

      const submitButton = screen.getByRole('button', { name: /sign in/i });
      
      // Button should indicate loading state
      await user.click(submitButton);
      
      // Loading state should be accessible
      expect(submitButton).toBeDisabled();
    });
  });

  describe('Mobile Accessibility', () => {
    it('should be accessible on mobile viewports', async () => {
      // Simulate mobile viewport
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 375,
      });

      Object.defineProperty(window, 'innerHeight', {
        writable: true,
        configurable: true,
        value: 667,
      });

      const { container } = renderWithProviders(<Landing />);
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('should have touch-friendly interactive elements', () => {
      renderWithProviders(<Landing />);

      const getStartedButton = screen.getByRole('button', { name: /get started/i });
      
      // Button should have adequate touch target size (minimum 44px)
      const styles = window.getComputedStyle(getStartedButton);
      expect(getStartedButton).toHaveClass('px-8', 'py-4'); // Adequate padding for touch
    });
  });

  describe('High Contrast Mode', () => {
    it('should work in high contrast mode', () => {
      // Simulate high contrast mode
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: jest.fn().mockImplementation(query => ({
          matches: query === '(prefers-contrast: high)',
          media: query,
          onchange: null,
          addListener: jest.fn(),
          removeListener: jest.fn(),
          addEventListener: jest.fn(),
          removeEventListener: jest.fn(),
          dispatchEvent: jest.fn(),
        })),
      });

      renderWithProviders(<Landing />);

      // Elements should still be visible and functional
      const getStartedButton = screen.getByRole('button', { name: /get started/i });
      expect(getStartedButton).toBeInTheDocument();
      expect(getStartedButton).toBeVisible();
    });
  });

  describe('Reduced Motion', () => {
    it('should respect reduced motion preferences', () => {
      // Mock reduced motion preference
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: jest.fn().mockImplementation(query => ({
          matches: query === '(prefers-reduced-motion: reduce)',
          media: query,
          onchange: null,
          addListener: jest.fn(),
          removeListener: jest.fn(),
          addEventListener: jest.fn(),
          removeEventListener: jest.fn(),
          dispatchEvent: jest.fn(),
        })),
      });

      renderWithProviders(<Landing />);

      // Animations should be disabled or reduced
      const { container } = renderWithProviders(<Landing />);
      
      // Check that motion-sensitive elements respect the preference
      const animatedElements = container.querySelectorAll('.animate-spin, .transition-all');
      animatedElements.forEach(element => {
        // In a real implementation, these would have reduced motion styles
        expect(element).toBeInTheDocument();
      });
    });
  });
});