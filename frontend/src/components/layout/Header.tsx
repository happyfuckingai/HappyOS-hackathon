import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTenant } from '../../contexts/TenantContext';
import { HeaderProps } from '../../types';

const Header: React.FC<HeaderProps> = ({ showMeetingControls = false, meetingId }) => {
  const { user, logout, isAuthenticated } = useAuth();
  const { currentTenant } = useTenant();
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/');
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  // Don't show header on landing page
  if (location.pathname === '/') {
    return null;
  }

  return (
    <header className="sticky top-0 z-50 glass-panel border-b border-white/10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo/Brand */}
          <div className="flex items-center">
            <button
              onClick={() => navigate(isAuthenticated ? '/lobby' : '/')}
              className="flex items-center space-x-3 text-xl font-display font-semibold text-white hover:opacity-80 transition-opacity duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/60 focus-visible:ring-offset-2 focus-visible:ring-offset-transparent rounded-lg px-2 py-1"
              aria-label={`${currentTenant?.branding.name || 'MeetMind'} Home`}
            >
              {currentTenant?.branding.logo && (
                <img
                  src={currentTenant.branding.logo}
                  alt={`${currentTenant.branding.name} Logo`}
                  className="h-8 w-auto"
                  onError={(e) => {
                    // Fallback to text if logo fails to load
                    e.currentTarget.style.display = 'none';
                  }}
                />
              )}
              <span 
                className="text-xl font-display font-semibold"
                style={{ color: currentTenant?.theme.primaryColor || '#2563eb' }}
              >
                {currentTenant?.branding.name || 'MeetMind'}
              </span>
            </button>
          </div>

          {/* Meeting Info - Hidden on mobile, shown on tablet+ */}
          {showMeetingControls && meetingId && (
            <div className="hidden sm:flex items-center space-x-4">
              <div className="glass-badge">
                <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" aria-hidden="true"></span>
                <span className="text-xs font-medium">Meeting: {meetingId}</span>
              </div>
            </div>
          )}

          {/* User Menu */}
          {isAuthenticated && user ? (
            <div className="flex items-center space-x-2 sm:space-x-4">
              <span className="hidden sm:block text-sm text-white/70 truncate max-w-32">
                {user.name}
              </span>
              <button
                onClick={handleLogout}
                className="glass-outline-button text-xs sm:text-xs"
                aria-label="Logout"
              >
                <span className="hidden sm:inline">Logout</span>
                <span className="sm:hidden">Exit</span>
              </button>
            </div>
          ) : (
            <button
              onClick={() => navigate('/auth')}
              className="glass-outline-button--accent text-xs sm:text-xs"
              aria-label="Sign in to your account"
            >
              Sign In
            </button>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;