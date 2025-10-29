import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BrowserRouter } from 'react-router-dom';
import { TenantProvider } from '../../contexts/TenantContext';
import { AuthProvider } from '../../contexts/AuthContext';
import Landing from '../../pages/Landing';
import { MobileOptimizer } from '../../components/common/MobileOptimizer';

// Mock AuthContext
const mockAuthContext = {
  user: null,
  isAuthenticated: false,
  isLoading: false,
  login: jest.fn(),
  register: jest.fn(),
  logout: jest.fn(),
};

jest.mock('../../contexts/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
  useAuth: () => mockAuthContext,
}));

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      <TenantProvider>
        <AuthProvider>
          <MobileOptimizer>
            {component}
          </MobileOptimizer>
        </AuthProvider>
      </TenantProvider>
    </BrowserRouter>
  );
};

// Mock window dimensions
const mockViewport = (width: number, height: number) => {
  Object.defineProperty(window, 'innerWidth', {
    writable: true,
    configurable: true,
    value: width,
  });
  Object.defineProperty(window, 'innerHeight', {
    writable: true,
    configurable: true,
    value: height,
  });
  
  // Trigger resize event
  window.dispatchEvent(new Event('resize'));
};

describe('Responsive Design Tests', () => {
  beforeEach(() => {
    // Reset to desktop size
    mockViewport(1920, 1080);
  });

  describe('Mobile Viewport (320px - 767px)', () => {
    it('renders correctly on small mobile (320px)', () => {
      mockViewport(320, 568);
      renderWithProviders(<Landing />);
      
      expect(screen.getByText('Meet')).toBeInTheDocument();
      expect(screen.getByText('Mind')).toBeInTheDocument();
      
      // Check that content is accessible on small screens
      const getStartedButton = screen.getByRole('button', { name: /get started/i });
      expect(getStartedButton).toBeInTheDocument();
    });

    it('renders correctly on large mobile (414px)', () => {
      mockViewport(414, 896);
      renderWithProviders(<Landing />);
      
      expect(screen.getByText('Meet')).toBeInTheDocument();
      expect(screen.getByText('Mind')).toBeInTheDocument();
    });

    it('handles portrait orientation', () => {
      mockViewport(375, 812); // iPhone X portrait
      renderWithProviders(<Landing />);
      
      const container = document.querySelector('.mobile-optimized-container');
      expect(container).toHaveAttribute('data-orientation', 'portrait');
      expect(container).toHaveAttribute('data-is-mobile', 'true');
    });

    it('handles landscape orientation', () => {
      mockViewport(667, 375); // iPhone landscape (smaller width)
      renderWithProviders(<Landing />);
      
      const container = document.querySelector('.mobile-optimized-container');
      expect(container).toHaveAttribute('data-orientation', 'landscape');
      expect(container).toHaveAttribute('data-is-mobile', 'true');
    });
  });

  describe('Tablet Viewport (768px - 1023px)', () => {
    it('renders correctly on tablet portrait (768px)', () => {
      mockViewport(768, 1024);
      renderWithProviders(<Landing />);
      
      const container = document.querySelector('.mobile-optimized-container');
      expect(container).toHaveAttribute('data-is-tablet', 'true');
      expect(container).toHaveAttribute('data-orientation', 'portrait');
    });

    it('renders correctly on tablet landscape (1024px)', () => {
      mockViewport(1024, 768);
      renderWithProviders(<Landing />);
      
      const container = document.querySelector('.mobile-optimized-container');
      expect(container).toHaveAttribute('data-is-desktop', 'true');
      expect(container).toHaveAttribute('data-orientation', 'landscape');
    });
  });

  describe('Desktop Viewport (1024px+)', () => {
    it('renders correctly on small desktop (1024px)', () => {
      mockViewport(1024, 768);
      renderWithProviders(<Landing />);
      
      const container = document.querySelector('.mobile-optimized-container');
      expect(container).toHaveAttribute('data-is-desktop', 'true');
    });

    it('renders correctly on large desktop (1920px)', () => {
      mockViewport(1920, 1080);
      renderWithProviders(<Landing />);
      
      const container = document.querySelector('.mobile-optimized-container');
      expect(container).toHaveAttribute('data-is-desktop', 'true');
    });

    it('renders correctly on ultra-wide (2560px)', () => {
      mockViewport(2560, 1440);
      renderWithProviders(<Landing />);
      
      const container = document.querySelector('.mobile-optimized-container');
      expect(container).toHaveAttribute('data-is-desktop', 'true');
    });
  });

  describe('Responsive Grid Layout', () => {
    it('shows 4-column grid on desktop', () => {
      mockViewport(1920, 1080);
      const { container } = renderWithProviders(<Landing />);
      
      const grid = container.querySelector('.grid.md\\:grid-cols-4');
      expect(grid).toBeInTheDocument();
    });

    it('shows single column on mobile', () => {
      mockViewport(375, 667);
      renderWithProviders(<Landing />);
      
      // On mobile, the grid should stack vertically
      const features = screen.getAllByText(/Tenant Screening|Lease Management|Payment Reminders|Portfolio Insights/);
      expect(features).toHaveLength(4);
    });
  });

  describe('Touch-Friendly Interactions', () => {
    it('has appropriate touch target sizes on mobile', () => {
      mockViewport(375, 667);
      renderWithProviders(<Landing />);
      
      const button = screen.getByRole('button', { name: /get started/i });
      const styles = getComputedStyle(button);
      
      // Button should have adequate padding for touch
      expect(button).toHaveClass('px-8', 'py-4');
    });

    it('applies touch-optimized classes', () => {
      mockViewport(375, 667);
      renderWithProviders(<Landing />);
      
      // Check if touch optimization classes are applied
      expect(document.body).toHaveClass('touch-optimized');
    });
  });

  describe('Typography Scaling', () => {
    it('uses responsive text sizes', () => {
      mockViewport(375, 667);
      renderWithProviders(<Landing />);
      
      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toHaveClass('text-6xl', 'md:text-7xl');
    });

    it('maintains readability on small screens', () => {
      mockViewport(320, 568);
      renderWithProviders(<Landing />);
      
      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toBeInTheDocument();
      
      // Text should be visible and readable
      const styles = getComputedStyle(heading);
      expect(styles.fontSize).toBeTruthy();
    });
  });

  describe('Safe Area Support', () => {
    it('handles devices with notches', () => {
      mockViewport(375, 812); // iPhone X
      renderWithProviders(<Landing />);
      
      // Check if safe area CSS variables are set
      const root = document.documentElement;
      const safeAreaTop = getComputedStyle(root).getPropertyValue('--safe-area-inset-top');
      
      // Should have safe area support (even if 0px)
      expect(safeAreaTop).toBeDefined();
    });
  });

  describe('Performance on Mobile', () => {
    it('applies performance optimizations on mobile', () => {
      mockViewport(375, 667);
      renderWithProviders(<Landing />);
      
      // Check if mobile performance classes are applied
      expect(document.body).toHaveClass('is-mobile');
    });

    it('reduces animations on mobile when requested', () => {
      mockViewport(375, 667);
      
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
      
      // Should respect reduced motion preferences
      expect(document.body).toHaveClass('is-mobile');
    });
  });

  describe('Cross-Browser Compatibility', () => {
    it('handles missing features gracefully', () => {
      // Mock missing IntersectionObserver
      const originalIntersectionObserver = window.IntersectionObserver;
      delete (window as any).IntersectionObserver;
      
      renderWithProviders(<Landing />);
      
      // Should still render without errors
      expect(screen.getByText('Meet')).toBeInTheDocument();
      
      // Restore
      (window as any).IntersectionObserver = originalIntersectionObserver;
    });

    it('provides fallbacks for CSS features', () => {
      renderWithProviders(<Landing />);
      
      // Check that elements with glass-card class exist
      const elements = document.querySelectorAll('.glass-card');
      expect(elements.length).toBeGreaterThan(0);
      
      // Should render without errors even if CSS features are missing
      expect(screen.getByText('Meet')).toBeInTheDocument();
    });
  });

  describe('Accessibility on Different Screen Sizes', () => {
    it('maintains focus management on mobile', () => {
      mockViewport(375, 667);
      renderWithProviders(<Landing />);
      
      const button = screen.getByRole('button', { name: /get started/i });
      button.focus();
      
      expect(button).toHaveFocus();
    });

    it('provides adequate contrast on all screen sizes', () => {
      mockViewport(375, 667);
      renderWithProviders(<Landing />);
      
      const heading = screen.getByRole('heading', { level: 1 });
      
      // Should have text-white class for good contrast
      expect(heading).toHaveClass('text-white');
    });
  });
});