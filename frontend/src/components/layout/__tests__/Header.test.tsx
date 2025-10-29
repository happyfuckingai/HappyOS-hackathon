import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BrowserRouter } from 'react-router-dom';
import Header from '../Header';
import { AuthProvider } from '../../../contexts/AuthContext';
import { TenantProvider } from '../../../contexts/TenantContext';

// Mock AuthContext
const mockAuthContext = {
  user: null,
  isAuthenticated: false,
  isLoading: false,
  login: jest.fn(),
  register: jest.fn(),
  logout: jest.fn(),
};

jest.mock('../../../contexts/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
  useAuth: () => mockAuthContext,
}));

// Mock useLocation with a default pathname
const mockPathname = '/lobby';
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useLocation: () => ({ pathname: mockPathname }),
}));

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      <TenantProvider>
        <AuthProvider>
          {component}
        </AuthProvider>
      </TenantProvider>
    </BrowserRouter>
  );
};

describe('Header', () => {
  beforeEach(() => {
    mockAuthContext.isAuthenticated = false;
    mockAuthContext.user = null;
  });

  it('renders MeetMind brand correctly on non-landing pages', () => {
    renderWithRouter(<Header />);

    expect(screen.getByText('MeetMind')).toBeInTheDocument();
  });

  it('has correct styling classes', () => {
    const { container } = renderWithRouter(<Header />);
    
    const header = container.querySelector('header');
    expect(header).toHaveClass('glass-panel', 'sticky', 'top-0', 'z-50');
  });

  it('renders brand as button with navigation', () => {
    renderWithRouter(<Header />);

    const brandButton = screen.getByRole('button', { name: 'MeetMind Home' });
    expect(brandButton).toBeInTheDocument();
  });

  it('shows meeting controls when showMeetingControls is true', () => {
    renderWithRouter(<Header showMeetingControls={true} meetingId="test-room-123" />);

    expect(screen.getByText('Meeting: test-room-123')).toBeInTheDocument();
  });

  it('does not show meeting controls by default', () => {
    renderWithRouter(<Header />);

    expect(screen.queryByText(/Meeting:/)).not.toBeInTheDocument();
  });

  it('shows sign in button when not authenticated', () => {
    mockAuthContext.isAuthenticated = false;
    renderWithRouter(<Header />);

    expect(screen.getByRole('button', { name: 'Sign in to your account' })).toBeInTheDocument();
  });

  it('shows user menu when authenticated', () => {
    mockAuthContext.isAuthenticated = true;
    mockAuthContext.user = { id: '1', name: 'Test User', email: 'test@example.com', role: 'user' };
    
    renderWithRouter(<Header />);

    expect(screen.getByText('Test User')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Logout' })).toBeInTheDocument();
  });
});