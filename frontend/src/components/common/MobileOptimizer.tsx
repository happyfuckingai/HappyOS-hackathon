import React, { useEffect, useState, useCallback } from 'react';

interface MobileOptimizerProps {
  children: React.ReactNode;
}

interface ViewportInfo {
  width: number;
  height: number;
  isMobile: boolean;
  isTablet: boolean;
  isDesktop: boolean;
  orientation: 'portrait' | 'landscape';
  devicePixelRatio: number;
}

/**
 * Mobile optimization component that handles responsive behavior,
 * touch interactions, and mobile-specific optimizations
 */
export const MobileOptimizer: React.FC<MobileOptimizerProps> = ({ children }) => {
  const [viewport, setViewport] = useState<ViewportInfo>(() => ({
    width: typeof window !== 'undefined' ? window.innerWidth : 1024,
    height: typeof window !== 'undefined' ? window.innerHeight : 768,
    isMobile: typeof window !== 'undefined' ? window.innerWidth < 768 : false,
    isTablet: typeof window !== 'undefined' ? window.innerWidth >= 768 && window.innerWidth < 1024 : false,
    isDesktop: typeof window !== 'undefined' ? window.innerWidth >= 1024 : true,
    orientation: typeof window !== 'undefined' && window.innerHeight > window.innerWidth ? 'portrait' : 'landscape',
    devicePixelRatio: typeof window !== 'undefined' ? window.devicePixelRatio : 1,
  }));

  // Update viewport information on resize
  const updateViewport = useCallback(() => {
    const width = window.innerWidth;
    const height = window.innerHeight;
    
    setViewport({
      width,
      height,
      isMobile: width < 768,
      isTablet: width >= 768 && width < 1024,
      isDesktop: width >= 1024,
      orientation: height > width ? 'portrait' : 'landscape',
      devicePixelRatio: window.devicePixelRatio || 1,
    });
  }, []);

  // Handle viewport changes
  useEffect(() => {
    const handleResize = () => {
      updateViewport();
    };

    const handleOrientationChange = () => {
      // Delay to ensure dimensions are updated after orientation change
      setTimeout(updateViewport, 100);
    };

    window.addEventListener('resize', handleResize);
    window.addEventListener('orientationchange', handleOrientationChange);

    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('orientationchange', handleOrientationChange);
    };
  }, [updateViewport]);

  // Set CSS custom properties for responsive design
  useEffect(() => {
    const root = document.documentElement;
    
    root.style.setProperty('--viewport-width', `${viewport.width}px`);
    root.style.setProperty('--viewport-height', `${viewport.height}px`);
    root.style.setProperty('--device-pixel-ratio', viewport.devicePixelRatio.toString());
    
    // Add viewport classes to body
    document.body.classList.toggle('is-mobile', viewport.isMobile);
    document.body.classList.toggle('is-tablet', viewport.isTablet);
    document.body.classList.toggle('is-desktop', viewport.isDesktop);
    document.body.classList.toggle('is-portrait', viewport.orientation === 'portrait');
    document.body.classList.toggle('is-landscape', viewport.orientation === 'landscape');
  }, [viewport]);

  // Handle touch interactions
  useEffect(() => {
    // Prevent zoom on double tap for iOS Safari
    let lastTouchEnd = 0;
    
    const preventZoom = (e: TouchEvent) => {
      const now = new Date().getTime();
      if (now - lastTouchEnd <= 300) {
        e.preventDefault();
      }
      lastTouchEnd = now;
    };

    // Add touch-friendly classes
    document.body.classList.add('touch-optimized');
    
    // Prevent zoom on double tap
    document.addEventListener('touchend', preventZoom, { passive: false });

    return () => {
      document.removeEventListener('touchend', preventZoom);
      document.body.classList.remove('touch-optimized');
    };
  }, []);

  // Handle safe area insets for devices with notches
  useEffect(() => {
    const updateSafeArea = () => {
      const root = document.documentElement;
      
      // Get safe area insets
      const safeAreaTop = getComputedStyle(root).getPropertyValue('--safe-area-inset-top') || '0px';
      const safeAreaBottom = getComputedStyle(root).getPropertyValue('--safe-area-inset-bottom') || '0px';
      const safeAreaLeft = getComputedStyle(root).getPropertyValue('--safe-area-inset-left') || '0px';
      const safeAreaRight = getComputedStyle(root).getPropertyValue('--safe-area-inset-right') || '0px';
      
      // Set CSS custom properties
      root.style.setProperty('--app-safe-area-top', safeAreaTop);
      root.style.setProperty('--app-safe-area-bottom', safeAreaBottom);
      root.style.setProperty('--app-safe-area-left', safeAreaLeft);
      root.style.setProperty('--app-safe-area-right', safeAreaRight);
    };

    updateSafeArea();
    window.addEventListener('resize', updateSafeArea);

    return () => {
      window.removeEventListener('resize', updateSafeArea);
    };
  }, []);

  // Optimize for mobile performance
  useEffect(() => {
    if (viewport.isMobile) {
      // Reduce animations on mobile for better performance
      document.body.classList.add('reduce-motion');
      
      // Optimize scroll behavior
      (document.body.style as any).webkitOverflowScrolling = 'touch';
      
      // Prevent pull-to-refresh on mobile
      (document.body.style as any).overscrollBehavior = 'none';
    } else {
      document.body.classList.remove('reduce-motion');
      (document.body.style as any).webkitOverflowScrolling = '';
      (document.body.style as any).overscrollBehavior = '';
    }
  }, [viewport.isMobile]);

  return (
    <div 
      className="mobile-optimized-container"
      data-viewport-width={viewport.width}
      data-viewport-height={viewport.height}
      data-is-mobile={viewport.isMobile}
      data-is-tablet={viewport.isTablet}
      data-is-desktop={viewport.isDesktop}
      data-orientation={viewport.orientation}
    >
      {children}
    </div>
  );
};

/**
 * Hook for accessing viewport information
 */
export const useViewport = () => {
  const [viewport, setViewport] = useState<ViewportInfo>(() => ({
    width: typeof window !== 'undefined' ? window.innerWidth : 1024,
    height: typeof window !== 'undefined' ? window.innerHeight : 768,
    isMobile: typeof window !== 'undefined' ? window.innerWidth < 768 : false,
    isTablet: typeof window !== 'undefined' ? window.innerWidth >= 768 && window.innerWidth < 1024 : false,
    isDesktop: typeof window !== 'undefined' ? window.innerWidth >= 1024 : true,
    orientation: typeof window !== 'undefined' && window.innerHeight > window.innerWidth ? 'portrait' : 'landscape',
    devicePixelRatio: typeof window !== 'undefined' ? window.devicePixelRatio : 1,
  }));

  useEffect(() => {
    const updateViewport = () => {
      const width = window.innerWidth;
      const height = window.innerHeight;
      
      setViewport({
        width,
        height,
        isMobile: width < 768,
        isTablet: width >= 768 && width < 1024,
        isDesktop: width >= 1024,
        orientation: height > width ? 'portrait' : 'landscape',
        devicePixelRatio: window.devicePixelRatio || 1,
      });
    };

    const handleResize = () => updateViewport();
    const handleOrientationChange = () => setTimeout(updateViewport, 100);

    window.addEventListener('resize', handleResize);
    window.addEventListener('orientationchange', handleOrientationChange);

    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('orientationchange', handleOrientationChange);
    };
  }, []);

  return viewport;
};

/**
 * Cross-browser compatibility utilities
 */
export const CrossBrowserUtils = {
  // Check for browser support
  supportsWebP: () => {
    const canvas = document.createElement('canvas');
    canvas.width = 1;
    canvas.height = 1;
    return canvas.toDataURL('image/webp').indexOf('data:image/webp') === 0;
  },

  supportsIntersectionObserver: () => {
    return 'IntersectionObserver' in window;
  },

  supportsServiceWorker: () => {
    return 'serviceWorker' in navigator;
  },

  // Get browser information
  getBrowserInfo: () => {
    const ua = navigator.userAgent;
    const isChrome = /Chrome/.test(ua) && /Google Inc/.test(navigator.vendor);
    const isSafari = /Safari/.test(ua) && /Apple Computer/.test(navigator.vendor);
    const isFirefox = /Firefox/.test(ua);
    const isEdge = /Edg/.test(ua);
    const isIOS = /iPad|iPhone|iPod/.test(ua);
    const isAndroid = /Android/.test(ua);

    return {
      isChrome,
      isSafari,
      isFirefox,
      isEdge,
      isIOS,
      isAndroid,
      isMobile: isIOS || isAndroid,
    };
  },

  // Apply browser-specific fixes
  applyBrowserFixes: () => {
    const browserInfo = CrossBrowserUtils.getBrowserInfo();
    
    // iOS Safari fixes
    if (browserInfo.isIOS && browserInfo.isSafari) {
      // Fix viewport height on iOS Safari
      const setVH = () => {
        const vh = window.innerHeight * 0.01;
        document.documentElement.style.setProperty('--vh', `${vh}px`);
      };
      
      setVH();
      window.addEventListener('resize', setVH);
      window.addEventListener('orientationchange', () => setTimeout(setVH, 100));
    }

    // Chrome mobile fixes
    if (browserInfo.isChrome && browserInfo.isMobile) {
      // Prevent zoom on input focus
      const inputs = document.querySelectorAll('input, select, textarea');
      inputs.forEach(input => {
        input.addEventListener('focus', () => {
          if (window.innerWidth < 768) {
            const viewport = document.querySelector('meta[name="viewport"]') as HTMLMetaElement;
            if (viewport) {
              viewport.content = 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no';
            }
          }
        });
        
        input.addEventListener('blur', () => {
          const viewport = document.querySelector('meta[name="viewport"]') as HTMLMetaElement;
          if (viewport) {
            viewport.content = 'width=device-width, initial-scale=1.0';
          }
        });
      });
    }
  },
};

export default MobileOptimizer;