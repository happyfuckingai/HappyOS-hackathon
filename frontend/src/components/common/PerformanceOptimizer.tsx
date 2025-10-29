import React, { useEffect, useCallback, useMemo } from 'react';
import { performanceMonitor, debounce, throttle } from '../../utils/performance';

interface PerformanceOptimizerProps {
  children: React.ReactNode;
  enableMonitoring?: boolean;
  enableLazyLoading?: boolean;
}

/**
 * Performance optimization wrapper component
 * Provides performance monitoring, lazy loading, and optimization utilities
 */
export const PerformanceOptimizer: React.FC<PerformanceOptimizerProps> = ({
  children,
  enableMonitoring = true,
  enableLazyLoading = true,
}) => {
  // Initialize performance monitoring
  useEffect(() => {
    if (enableMonitoring && process.env.NODE_ENV === 'development') {
      console.log('Performance monitoring enabled');
      
      // Log performance metrics periodically
      const logMetrics = () => {
        const metrics = performanceMonitor.getAverageMetrics();
        if (metrics) {
          console.log('Performance Metrics:', metrics);
        }
      };

      const interval = setInterval(logMetrics, 30000); // Every 30 seconds
      
      return () => {
        clearInterval(interval);
        performanceMonitor.disconnect();
      };
    }
  }, [enableMonitoring]);

  // Intersection Observer for lazy loading
  const intersectionObserver = useMemo(() => {
    if (!enableLazyLoading || typeof IntersectionObserver === 'undefined') {
      return null;
    }

    return new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const target = entry.target as HTMLElement;
            
            // Handle lazy loading of images
            if (target.tagName === 'IMG' && target.dataset.src) {
              (target as HTMLImageElement).src = target.dataset.src;
              target.removeAttribute('data-src');
            }
            
            // Handle lazy loading of components
            if (target.dataset.lazyComponent) {
              target.style.visibility = 'visible';
            }
          }
        });
      },
      {
        rootMargin: '50px',
        threshold: 0.1,
      }
    );
  }, [enableLazyLoading]);

  // Cleanup intersection observer
  useEffect(() => {
    return () => {
      if (intersectionObserver) {
        intersectionObserver.disconnect();
      }
    };
  }, [intersectionObserver]);

  // Performance optimization hooks
  const optimizedScrollHandler = useCallback(
    throttle(() => {
      // Handle scroll-based optimizations
      const scrollY = window.scrollY;
      
      // Lazy load images in viewport
      if (intersectionObserver) {
        const lazyImages = document.querySelectorAll('img[data-src]');
        lazyImages.forEach((img) => {
          intersectionObserver.observe(img);
        });
      }
    }, 100),
    [intersectionObserver]
  );

  const optimizedResizeHandler = useCallback(
    debounce(() => {
      // Handle resize-based optimizations
      performanceMonitor.measureCustom('resize-handler', () => {
        // Trigger re-layout optimizations
        const event = new CustomEvent('optimized-resize');
        window.dispatchEvent(event);
      });
    }, 250),
    []
  );

  // Attach optimized event listeners
  useEffect(() => {
    window.addEventListener('scroll', optimizedScrollHandler, { passive: true });
    window.addEventListener('resize', optimizedResizeHandler);

    return () => {
      window.removeEventListener('scroll', optimizedScrollHandler);
      window.removeEventListener('resize', optimizedResizeHandler);
    };
  }, [optimizedScrollHandler, optimizedResizeHandler]);

  // Memory cleanup on unmount
  useEffect(() => {
    return () => {
      // Clear any remaining timeouts/intervals
      // This helps prevent memory leaks
      const highestTimeoutId = window.setTimeout(() => {}, 0);
      for (let i = 0; i < Number(highestTimeoutId); i++) {
        clearTimeout(i);
      }
    };
  }, []);

  return <>{children}</>;
};

/**
 * HOC for performance optimization
 */
export const withPerformanceOptimization = <P extends object>(
  Component: React.ComponentType<P>
) => {
  const OptimizedComponent = React.memo((props: P) => {
    return (
      <PerformanceOptimizer>
        <Component {...props} />
      </PerformanceOptimizer>
    );
  });

  OptimizedComponent.displayName = `withPerformanceOptimization(${
    Component.displayName || Component.name
  })`;

  return OptimizedComponent;
};

/**
 * Hook for performance monitoring
 */
export const usePerformanceMonitoring = () => {
  const measureRender = useCallback((componentName: string) => {
    return (fn: () => void) => {
      performanceMonitor.measureCustom(`${componentName}-render`, fn);
    };
  }, []);

  const getMetrics = useCallback(() => {
    return performanceMonitor.getAverageMetrics();
  }, []);

  return {
    measureRender,
    getMetrics,
  };
};

/**
 * Lazy image component with performance optimization
 */
export const LazyImage: React.FC<{
  src: string;
  alt: string;
  className?: string;
  placeholder?: string;
}> = ({ src, alt, className, placeholder }) => {
  const [loaded, setLoaded] = React.useState(false);
  const [inView, setInView] = React.useState(false);
  const imgRef = React.useRef<HTMLImageElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { threshold: 0.1 }
    );

    if (imgRef.current) {
      observer.observe(imgRef.current);
    }

    return () => observer.disconnect();
  }, []);

  return (
    <div className={`relative ${className}`}>
      {!loaded && placeholder && (
        <div className="absolute inset-0 bg-gray-200 animate-pulse rounded" />
      )}
      <img
        ref={imgRef}
        src={inView ? src : undefined}
        alt={alt}
        className={`transition-opacity duration-300 ${
          loaded ? 'opacity-100' : 'opacity-0'
        } ${className}`}
        onLoad={() => setLoaded(true)}
        loading="lazy"
      />
    </div>
  );
};

export default PerformanceOptimizer;