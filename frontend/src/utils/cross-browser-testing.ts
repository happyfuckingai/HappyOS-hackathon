/**
 * Cross-browser testing and compatibility utilities
 */

export interface BrowserInfo {
  name: string;
  version: string;
  engine: string;
  platform: string;
  isMobile: boolean;
  isTablet: boolean;
  isDesktop: boolean;
  supportsFeatures: {
    webp: boolean;
    intersectionObserver: boolean;
    serviceWorker: boolean;
    webGL: boolean;
    localStorage: boolean;
    sessionStorage: boolean;
    indexedDB: boolean;
    webRTC: boolean;
    mediaDevices: boolean;
    geolocation: boolean;
    notifications: boolean;
    fullscreen: boolean;
    clipboard: boolean;
  };
}

/**
 * Detect browser information and capabilities
 */
export const detectBrowser = (): BrowserInfo => {
  const ua = navigator.userAgent;
  const platform = navigator.platform;
  
  // Browser detection
  let name = 'Unknown';
  let version = 'Unknown';
  let engine = 'Unknown';
  
  if (ua.includes('Chrome') && !ua.includes('Edg')) {
    name = 'Chrome';
    const match = ua.match(/Chrome\/(\d+)/);
    version = match ? match[1] : 'Unknown';
    engine = 'Blink';
  } else if (ua.includes('Safari') && !ua.includes('Chrome')) {
    name = 'Safari';
    const match = ua.match(/Version\/(\d+)/);
    version = match ? match[1] : 'Unknown';
    engine = 'WebKit';
  } else if (ua.includes('Firefox')) {
    name = 'Firefox';
    const match = ua.match(/Firefox\/(\d+)/);
    version = match ? match[1] : 'Unknown';
    engine = 'Gecko';
  } else if (ua.includes('Edg')) {
    name = 'Edge';
    const match = ua.match(/Edg\/(\d+)/);
    version = match ? match[1] : 'Unknown';
    engine = 'Blink';
  }
  
  // Device type detection
  const isMobile = /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(ua);
  const isTablet = /iPad|Android(?!.*Mobile)/i.test(ua);
  const isDesktop = !isMobile && !isTablet;
  
  // Feature detection
  const supportsFeatures = {
    webp: checkWebPSupport(),
    intersectionObserver: 'IntersectionObserver' in window,
    serviceWorker: 'serviceWorker' in navigator,
    webGL: checkWebGLSupport(),
    localStorage: checkLocalStorageSupport(),
    sessionStorage: checkSessionStorageSupport(),
    indexedDB: 'indexedDB' in window,
    webRTC: checkWebRTCSupport(),
    mediaDevices: 'mediaDevices' in navigator,
    geolocation: 'geolocation' in navigator,
    notifications: 'Notification' in window,
    fullscreen: checkFullscreenSupport(),
    clipboard: 'clipboard' in navigator,
  };
  
  return {
    name,
    version,
    engine,
    platform,
    isMobile,
    isTablet,
    isDesktop,
    supportsFeatures,
  };
};

/**
 * Feature detection functions
 */
function checkWebPSupport(): boolean {
  try {
    const canvas = document.createElement('canvas');
    canvas.width = 1;
    canvas.height = 1;
    return canvas.toDataURL('image/webp').indexOf('data:image/webp') === 0;
  } catch {
    return false;
  }
}

function checkWebGLSupport(): boolean {
  try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    return !!gl;
  } catch {
    return false;
  }
}

function checkLocalStorageSupport(): boolean {
  try {
    const test = 'test';
    localStorage.setItem(test, test);
    localStorage.removeItem(test);
    return true;
  } catch {
    return false;
  }
}

function checkSessionStorageSupport(): boolean {
  try {
    const test = 'test';
    sessionStorage.setItem(test, test);
    sessionStorage.removeItem(test);
    return true;
  } catch {
    return false;
  }
}

function checkWebRTCSupport(): boolean {
  return !!(
    window.RTCPeerConnection ||
    (window as any).webkitRTCPeerConnection ||
    (window as any).mozRTCPeerConnection
  );
}

function checkFullscreenSupport(): boolean {
  return !!(
    document.fullscreenEnabled ||
    (document as any).webkitFullscreenEnabled ||
    (document as any).mozFullScreenEnabled ||
    (document as any).msFullscreenEnabled
  );
}

/**
 * Cross-browser polyfills and fixes
 */
export const applyPolyfills = () => {
  // Intersection Observer polyfill
  if (!('IntersectionObserver' in window)) {
    console.warn('IntersectionObserver not supported, consider adding polyfill');
  }
  
  // ResizeObserver polyfill
  if (!('ResizeObserver' in window)) {
    console.warn('ResizeObserver not supported, consider adding polyfill');
  }
  
  // Custom event polyfill for IE
  if (typeof (window as any).CustomEvent !== 'function') {
    (window as any).CustomEvent = function(event: string, params: any) {
      params = params || { bubbles: false, cancelable: false, detail: undefined };
      const evt = document.createEvent('CustomEvent');
      evt.initCustomEvent(event, params.bubbles, params.cancelable, params.detail);
      return evt;
    };
  }
  
  // Object.assign polyfill
  if (typeof Object.assign !== 'function') {
    Object.assign = function(target: any, ...sources: any[]) {
      if (target == null) {
        throw new TypeError('Cannot convert undefined or null to object');
      }
      
      const to = Object(target);
      
      for (let index = 0; index < sources.length; index++) {
        const nextSource = sources[index];
        
        if (nextSource != null) {
          for (const nextKey in nextSource) {
            if (Object.prototype.hasOwnProperty.call(nextSource, nextKey)) {
              to[nextKey] = nextSource[nextKey];
            }
          }
        }
      }
      return to;
    };
  }
};

/**
 * Browser-specific optimizations
 */
export const applyBrowserOptimizations = () => {
  const browser = detectBrowser();
  
  // Safari-specific optimizations
  if (browser.name === 'Safari') {
    // Fix for Safari's aggressive caching
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.getRegistrations().then(registrations => {
        registrations.forEach(registration => {
          registration.update();
        });
      });
    }
    
    // Fix for Safari's viewport height issue
    const setVH = () => {
      const vh = window.innerHeight * 0.01;
      document.documentElement.style.setProperty('--vh', `${vh}px`);
    };
    
    setVH();
    window.addEventListener('resize', setVH);
    window.addEventListener('orientationchange', () => setTimeout(setVH, 100));
  }
  
  // Chrome-specific optimizations
  if (browser.name === 'Chrome') {
    // Enable hardware acceleration for better performance
    document.body.style.transform = 'translateZ(0)';
    
    // Optimize for Chrome's aggressive garbage collection
    if (browser.isMobile) {
      // Reduce memory usage on mobile Chrome
      document.body.classList.add('chrome-mobile-optimized');
    }
  }
  
  // Firefox-specific optimizations
  if (browser.name === 'Firefox') {
    // Firefox-specific CSS optimizations
    document.body.classList.add('firefox-optimized');
  }
  
  // Edge-specific optimizations
  if (browser.name === 'Edge') {
    // Edge-specific optimizations
    document.body.classList.add('edge-optimized');
  }
  
  // Mobile-specific optimizations
  if (browser.isMobile) {
    // Prevent zoom on input focus
    const viewport = document.querySelector('meta[name="viewport"]') as HTMLMetaElement;
    if (viewport) {
      const inputs = document.querySelectorAll('input, select, textarea');
      
      inputs.forEach(input => {
        input.addEventListener('focus', () => {
          viewport.content = 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no';
        });
        
        input.addEventListener('blur', () => {
          viewport.content = 'width=device-width, initial-scale=1.0';
        });
      });
    }
    
    // Optimize touch interactions
    document.body.style.touchAction = 'manipulation';
    (document.body.style as any).webkitTapHighlightColor = 'transparent';
  }
};

/**
 * Performance testing utilities
 */
export const runPerformanceTests = () => {
  const results = {
    renderTime: 0,
    domContentLoaded: 0,
    firstContentfulPaint: 0,
    largestContentfulPaint: 0,
    cumulativeLayoutShift: 0,
    firstInputDelay: 0,
  };
  
  // Measure render time
  const startTime = performance.now();
  requestAnimationFrame(() => {
    results.renderTime = performance.now() - startTime;
  });
  
  // Get navigation timing
  if (performance.getEntriesByType) {
    const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    if (navigation) {
      results.domContentLoaded = navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart;
    }
  }
  
  // Get paint timing
  if (performance.getEntriesByType) {
    const paintEntries = performance.getEntriesByType('paint');
    paintEntries.forEach(entry => {
      if (entry.name === 'first-contentful-paint') {
        results.firstContentfulPaint = entry.startTime;
      }
    });
  }
  
  // Web Vitals (if available)
  if ('PerformanceObserver' in window) {
    try {
      // Largest Contentful Paint
      const lcpObserver = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        const lastEntry = entries[entries.length - 1];
        results.largestContentfulPaint = lastEntry.startTime;
      });
      lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] });
      
      // Cumulative Layout Shift
      const clsObserver = new PerformanceObserver((list) => {
        let clsValue = 0;
        for (const entry of list.getEntries()) {
          if (!(entry as any).hadRecentInput) {
            clsValue += (entry as any).value;
          }
        }
        results.cumulativeLayoutShift = clsValue;
      });
      clsObserver.observe({ entryTypes: ['layout-shift'] });
      
      // First Input Delay
      const fidObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          results.firstInputDelay = (entry as any).processingStart - entry.startTime;
        }
      });
      fidObserver.observe({ entryTypes: ['first-input'] });
      
    } catch (error) {
      console.warn('Performance Observer not fully supported:', error);
    }
  }
  
  return results;
};

/**
 * Accessibility testing utilities
 */
export const runAccessibilityTests = () => {
  const issues: string[] = [];
  
  // Check for missing alt attributes
  const images = document.querySelectorAll('img:not([alt])');
  if (images.length > 0) {
    issues.push(`${images.length} images missing alt attributes`);
  }
  
  // Check for missing form labels
  const inputs = document.querySelectorAll('input:not([aria-label]):not([aria-labelledby])');
  inputs.forEach(input => {
    const id = input.getAttribute('id');
    if (!id || !document.querySelector(`label[for="${id}"]`)) {
      issues.push('Input missing associated label');
    }
  });
  
  // Check for heading hierarchy
  const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
  let previousLevel = 0;
  headings.forEach(heading => {
    const level = parseInt(heading.tagName.charAt(1));
    if (level > previousLevel + 1) {
      issues.push('Heading hierarchy skipped a level');
    }
    previousLevel = level;
  });
  
  // Check for color contrast (basic check)
  const elements = document.querySelectorAll('*');
  elements.forEach(element => {
    const styles = getComputedStyle(element);
    const color = styles.color;
    const backgroundColor = styles.backgroundColor;
    
    // This is a simplified check - in production, use a proper contrast ratio calculator
    if (color === backgroundColor) {
      issues.push('Potential color contrast issue detected');
    }
  });
  
  return issues;
};

/**
 * Initialize cross-browser optimizations
 */
export const initializeCrossBrowserSupport = () => {
  // Apply polyfills
  applyPolyfills();
  
  // Apply browser-specific optimizations
  applyBrowserOptimizations();
  
  // Log browser information in development
  if (process.env.NODE_ENV === 'development') {
    const browserInfo = detectBrowser();
    console.log('Browser Info:', browserInfo);
    
    // Run performance tests
    setTimeout(() => {
      const perfResults = runPerformanceTests();
      console.log('Performance Results:', perfResults);
    }, 1000);
    
    // Run accessibility tests
    setTimeout(() => {
      const a11yIssues = runAccessibilityTests();
      if (a11yIssues.length > 0) {
        console.warn('Accessibility Issues:', a11yIssues);
      }
    }, 2000);
  }
};