import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BrowserRouter } from 'react-router-dom';
import Landing from '../Landing';
import { AuthProvider } from '../../contexts/AuthContext';

// Mock useNavigate
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

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

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      <AuthProvider>
        {component}
      </AuthProvider>
    </BrowserRouter>
  );
};

describe('Landing', () => {
  beforeEach(() => {
    mockNavigate.mockClear();
    mockAuthContext.isAuthenticated = false;
  });

  it('renders hero section correctly', () => {
    renderWithRouter(<Landing />);

    expect(screen.getByText('Meet')).toBeInTheDocument();
    expect(screen.getByText('Mind')).toBeInTheDocument();
    expect(screen.getByText(/Autonomous property management assistant/)).toBeInTheDocument();
  });

  it('renders get started button', () => {
    renderWithRouter(<Landing />);

    const getStartedButton = screen.getByRole('button', { name: /get started/i });
    expect(getStartedButton).toBeInTheDocument();
  });

  it('navigates to auth page when not authenticated', () => {
    mockAuthContext.isAuthenticated = false;
    renderWithRouter(<Landing />);

    const getStartedButton = screen.getByRole('button', { name: /get started/i });
    fireEvent.click(getStartedButton);

    expect(mockNavigate).toHaveBeenCalledWith('/auth');
  });

  it('navigates to lobby when authenticated', () => {
    mockAuthContext.isAuthenticated = true;
    renderWithRouter(<Landing />);

    const getStartedButton = screen.getByRole('button', { name: /get started/i });
    fireEvent.click(getStartedButton);

    expect(mockNavigate).toHaveBeenCalledWith('/lobby');
  });

  it('renders feature cards', () => {
    renderWithRouter(<Landing />);

    expect(screen.getByText('Tenant Screening')).toBeInTheDocument();
    expect(screen.getByText('Lease Management')).toBeInTheDocument();
    expect(screen.getByText('Payment Reminders')).toBeInTheDocument();
    expect(screen.getByText('Portfolio Insights')).toBeInTheDocument();

    expect(screen.getByText(/AI-powered risk assessment/)).toBeInTheDocument();
    expect(screen.getByText(/Instant Q&A on lease agreements/)).toBeInTheDocument();
    expect(screen.getByText(/Automated late payment notifications/)).toBeInTheDocument();
    expect(screen.getByText(/Real-time analytics on delinquency rates/)).toBeInTheDocument();
  });

  it('has correct styling classes', () => {
    const { container } = renderWithRouter(<Landing />);

    const heroTitle = screen.getByRole('heading', { level: 1 });
    expect(heroTitle).toHaveClass('text-6xl', 'md:text-7xl', 'font-display', 'font-bold');

    const mindSpan = screen.getByText('Mind');
    expect(mindSpan).toHaveClass('text-orange-500');

    const getStartedButton = screen.getByRole('button', { name: /get started/i });
    expect(getStartedButton).toHaveClass('bg-orange-500');
  });

  it('renders feature icons', () => {
    const { container } = renderWithRouter(<Landing />);

    // Check for SVG icons in feature cards
    const svgElements = container.querySelectorAll('svg');
    expect(svgElements.length).toBeGreaterThan(0);
  });

  it('has responsive design classes', () => {
    renderWithRouter(<Landing />);

    const heroTitle = screen.getByRole('heading', { level: 1 });
    expect(heroTitle).toHaveClass('text-6xl', 'md:text-7xl');

    const heroDescription = screen.getByText(/Autonomous property management assistant/);
    expect(heroDescription).toHaveClass('text-xl', 'md:text-2xl');
  });

  it('renders grid layout for features', () => {
    const { container } = renderWithRouter(<Landing />);

    const featuresGrid = container.querySelector('.grid.md\\:grid-cols-4');
    expect(featuresGrid).toBeInTheDocument();
  });
});