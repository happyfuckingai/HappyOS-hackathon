import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const Landing: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const handleGetStarted = () => {
    if (isAuthenticated) {
      navigate('/lobby');
    } else {
      navigate('/auth');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="max-w-4xl mx-auto text-center">
        {/* Hero Section */}
        <div className="mb-12">
          <h1 className="text-6xl md:text-7xl font-display font-bold text-white mb-4">
            Meet<span className="text-orange-500">Mind</span>
            <span className="text-blue-400"> | RentOps</span>
          </h1>
          <p className="text-lg md:text-xl text-white/60 mb-2 font-medium">
            Powered by Agent Svea
          </p>
          <p className="text-xl md:text-2xl text-white/70 mb-8 max-w-2xl mx-auto">
            Autonomous property management assistant that streamlines tenant screening, lease management, and portfolio insights
          </p>
        </div>

        {/* CTA Button */}
        <div className="mb-16">
          <button
            onClick={handleGetStarted}
            className="inline-flex items-center px-8 py-4 text-lg font-semibold text-white bg-orange-500 rounded-full hover:bg-orange-600 transition-all duration-200 shadow-glow-orange hover:shadow-lg transform hover:scale-105"
          >
            Get Started
            <svg 
              className="ml-2 w-5 h-5" 
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path 
                strokeLinecap="round" 
                strokeLinejoin="round" 
                strokeWidth={2} 
                d="M13 7l5 5m0 0l-5 5m5-5H6" 
              />
            </svg>
          </button>
        </div>

        {/* Features */}
        <div className="grid md:grid-cols-4 gap-6 max-w-5xl mx-auto">
          <div className="glass-card p-6 text-center">
            <div className="w-12 h-12 bg-orange-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">Tenant Screening</h3>
            <p className="text-white/60 text-sm">
              AI-powered risk assessment with affordability ratios and credit analysis
            </p>
          </div>

          <div className="glass-card p-6 text-center">
            <div className="w-12 h-12 bg-blue-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">Lease Management</h3>
            <p className="text-white/60 text-sm">
              Instant Q&A on lease agreements with confidence scoring and citations
            </p>
          </div>

          <div className="glass-card p-6 text-center">
            <div className="w-12 h-12 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">Payment Reminders</h3>
            <p className="text-white/60 text-sm">
              Automated late payment notifications with personalized payment plans
            </p>
          </div>

          <div className="glass-card p-6 text-center">
            <div className="w-12 h-12 bg-purple-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 00-2-2z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-white mb-2">Portfolio Insights</h3>
            <p className="text-white/60 text-sm">
              Real-time analytics on delinquency rates, vacancy risk, and actionable recommendations
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Landing;