import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { MeetingProvider } from './contexts/MeetingContext';
import { SSEProvider } from './contexts/SSEContext';
import { WebSocketProvider } from './contexts/WebSocketContext';
import { UIResourceProvider } from './contexts/UIResourceContext';
import { TenantProvider } from './contexts/TenantContext';
import AppShell from './components/layout/AppShell';
import AuthGuard from './components/auth/AuthGuard';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { NetworkErrorHandler } from './components/common/NetworkErrorHandler';
import { AccessibilityProvider } from './components/common/AccessibilityProvider';
import { PerformanceOptimizer } from './components/common/PerformanceOptimizer';
import { MobileOptimizer } from './components/common/MobileOptimizer';

// Lazy load pages for better performance with chunk names for better caching
const Landing = lazy(() => import(/* webpackChunkName: "landing" */ './pages/Landing'));
const Auth = lazy(() => import(/* webpackChunkName: "auth" */ './pages/Auth'));
const Lobby = lazy(() => import(/* webpackChunkName: "lobby" */ './pages/Lobby'));
const Meeting = lazy(() => import(/* webpackChunkName: "meeting" */ './pages/Meeting'));
const UIResourceDemo = lazy(() => import(/* webpackChunkName: "ui-demo" */ './pages/UIResourceDemo'));

// Enhanced loading fallback component
const PageLoader: React.FC<{ page?: string }> = ({ page = 'page' }) => (
  <div className="min-h-screen flex items-center justify-center">
    <div className="glass-card p-8 text-center max-w-md mx-4">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500 mx-auto mb-4"></div>
      <h3 className="text-lg font-semibold text-white mb-2">Loading {page}</h3>
      <p className="text-white/60 text-sm">Please wait while we prepare your experience</p>
    </div>
  </div>
);

function App() {
  return (
    <ErrorBoundary>
      <NetworkErrorHandler>
        <AccessibilityProvider>
          <PerformanceOptimizer enableMonitoring={process.env.NODE_ENV === 'development'}>
            <MobileOptimizer>
              <div className="app-root">
              <TenantProvider>
                <AuthProvider>
            <MeetingProvider>
              <SSEProvider>
                <WebSocketProvider>
                  <UIResourceProvider>
                  <Router>
                  <AppShell>
                  <Routes>
                    <Route 
                      path="/" 
                      element={
                        <Suspense fallback={<PageLoader page="landing page" />}>
                          <Landing />
                        </Suspense>
                      } 
                    />
                    <Route 
                      path="/auth" 
                      element={
                        <Suspense fallback={<PageLoader page="authentication" />}>
                          <Auth />
                        </Suspense>
                      } 
                    />
                    <Route 
                      path="/lobby" 
                      element={
                        <AuthGuard fallback={<PageLoader page="authentication" />}>
                          <Suspense fallback={<PageLoader page="lobby" />}>
                            <Lobby />
                          </Suspense>
                        </AuthGuard>
                      } 
                    />
                    <Route 
                      path="/meeting/:roomId" 
                      element={
                        <AuthGuard fallback={<PageLoader page="authentication" />}>
                          <Suspense fallback={<PageLoader page="meeting room" />}>
                            <Meeting />
                          </Suspense>
                        </AuthGuard>
                      } 
                    />
                    <Route 
                      path="/ui-demo" 
                      element={
                        <Suspense fallback={<PageLoader page="UI demo" />}>
                          <UIResourceDemo />
                        </Suspense>
                      } 
                    />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                  </AppShell>
                  </Router>
                  </UIResourceProvider>
                </WebSocketProvider>
              </SSEProvider>
            </MeetingProvider>
                </AuthProvider>
              </TenantProvider>
              </div>
            </MobileOptimizer>
          </PerformanceOptimizer>
        </AccessibilityProvider>
      </NetworkErrorHandler>
    </ErrorBoundary>
  );
}

export default App;