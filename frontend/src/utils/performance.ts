/**
 * Performance monitoring and optimization utilities
 */

import React from 'react';

// Performance metrics collection
export interface PerformanceMetrics {
  loadTime: number;
  renderTime: number;
  interactionTime: number;
  memoryUsage?: number;
}

// Performance observer for monitoring
export class PerformanceMonitor {
  private metrics: PerformanceMetrics[] = [];
  private observer?: PerformanceObserver;

  constructor() {
    this.initializeObserver();
  }

  private initializeObserver() {
    if ('PerformanceObserver' in window) {
      this.observer = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        entries.forEach((entry) => {
          this.processEntry(entry);
        });
      });

      // Observe navigation, paint, and measure entries
      try {
        this.observer.observe({ entryTypes: ['navigation', 'paint', 'measure'] });
      } catch (e) {
        console.warn('Performance observer not fully supported:', e);
      }
    }
  }

  private processEntry(entry: PerformanceEntry) {
    switch (entry.entryType) {
      case 'navigation':
        const navEntry = entry as PerformanceNavigationTiming;
        this.recordMetric({
          loadTime: navEntry.loadEventEnd - navEntry.loadEventStart,
          renderTime: navEntry.domContentLoadedEventEnd - navEntry.domContentLoadedEventStart,
          interactionTime: navEntry.domInteractive - navEntry.fetchStart,
        });
        break;
      case 'paint':
        if (entry.name === 'first-contentful-paint') {
          console.log(`First Contentful Paint: ${entry.startTime}ms`);
        }
        break;
      case 'measure':
        console.log(`Custom measure ${entry.name}: ${entry.duration}ms`);
        break;
    }
  }

  private recordMetric(metric: PerformanceMetrics) {
    this.metrics.push(metric);
    
    // Keep only last 10 metrics
    if (this.metrics.length > 10) {
      this.metrics.shift();
    }
  }

  public getAverageMetrics(): PerformanceMetrics | null {
    if (this.metrics.length === 0) return null;

    const avg = this.metrics.reduce(
      (acc, metric) => ({
        loadTime: acc.loadTime + metric.loadTime,
        renderTime: acc.renderTime + metric.renderTime,
        interactionTime: acc.interactionTime + metric.interactionTime,
      }),
      { loadTime: 0, renderTime: 0, interactionTime: 0 }
    );

    return {
      loadTime: avg.loadTime / this.metrics.length,
      renderTime: avg.renderTime / this.metrics.length,
      interactionTime: avg.interactionTime / this.metrics.length,
    };
  }

  public measureCustom(name: string, fn: () => void) {
    performance.mark(`${name}-start`);
    fn();
    performance.mark(`${name}-end`);
    performance.measure(name, `${name}-start`, `${name}-end`);
  }

  public disconnect() {
    if (this.observer) {
      this.observer.disconnect();
    }
  }
}

// Bundle size analyzer
export const analyzeBundleSize = () => {
  if (process.env.NODE_ENV === 'development') {
    const scripts = Array.from(document.querySelectorAll('script[src]'));
    const totalSize = scripts.reduce((size, script) => {
      const src = (script as HTMLScriptElement).src;
      if (src.includes('chunk') || src.includes('bundle')) {
        // Estimate size based on typical chunk sizes
        return size + 100; // KB estimate
      }
      return size;
    }, 0);
    
    console.log(`Estimated bundle size: ${totalSize}KB`);
    return totalSize;
  }
  return 0;
};

// Memory usage monitoring
export const getMemoryUsage = (): number | null => {
  if ('memory' in performance) {
    const memory = (performance as any).memory;
    return memory.usedJSHeapSize / 1024 / 1024; // MB
  }
  return null;
};

// Lazy loading helper
export const createLazyComponent = <T extends React.ComponentType<any>>(
  importFn: () => Promise<{ default: T }>
) => {
  return React.lazy(importFn);
};

// Image optimization helper
export const optimizeImage = (src: string, width?: number, height?: number): string => {
  // In a real app, this would integrate with image optimization services
  // For now, just return the original src
  return src;
};

// Debounce utility for performance
export const debounce = <T extends (...args: any[]) => any>(
  func: T,
  wait: number
): ((...args: Parameters<T>) => void) => {
  let timeout: NodeJS.Timeout;
  
  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
};

// Throttle utility for performance
export const throttle = <T extends (...args: any[]) => any>(
  func: T,
  limit: number
): ((...args: Parameters<T>) => void) => {
  let inThrottle: boolean;
  
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
};

// Global performance monitor instance
export const performanceMonitor = new PerformanceMonitor();