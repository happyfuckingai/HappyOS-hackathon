import React from 'react';
import { Settings, Eye, Type, Contrast } from 'lucide-react';
import { useAccessibility } from './AccessibilityProvider';

interface AccessibilitySettingsProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AccessibilitySettings: React.FC<AccessibilitySettingsProps> = ({
  isOpen,
  onClose,
}) => {
  const {
    isHighContrast,
    fontSize,
    toggleHighContrast,
    setFontSize,
    announceToScreenReader,
  } = useAccessibility();

  if (!isOpen) return null;

  const handleFontSizeChange = (size: 'small' | 'medium' | 'large') => {
    setFontSize(size);
    announceToScreenReader(`Font size changed to ${size}`);
  };

  const handleHighContrastToggle = () => {
    toggleHighContrast();
    announceToScreenReader(
      `High contrast mode ${!isHighContrast ? 'enabled' : 'disabled'}`
    );
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="accessibility-settings-title"
    >
      <div className="glass-card max-w-md w-full mx-4">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Settings className="h-5 w-5 text-orange-400" aria-hidden="true" />
            <h2 id="accessibility-settings-title" className="text-lg font-semibold text-white">
              Accessibility Settings
            </h2>
          </div>
          <button
            onClick={onClose}
            className="glass-button p-2"
            aria-label="Close accessibility settings"
          >
            ×
          </button>
        </div>

        <div className="space-y-6">
          {/* Font Size */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Type className="h-4 w-4 text-orange-400" aria-hidden="true" />
              <label className="text-sm font-medium text-white">
                Font Size
              </label>
            </div>
            <div
              className="flex gap-2"
              role="radiogroup"
              aria-labelledby="font-size-label"
            >
              {(['small', 'medium', 'large'] as const).map((size) => (
                <button
                  key={size}
                  onClick={() => handleFontSizeChange(size)}
                  className={`glass-button px-3 py-2 text-sm capitalize ${
                    fontSize === size
                      ? 'bg-orange-500/20 border-orange-500/60 text-orange-100'
                      : ''
                  }`}
                  role="radio"
                  aria-checked={fontSize === size}
                  aria-label={`Set font size to ${size}`}
                >
                  {size}
                </button>
              ))}
            </div>
          </div>

          {/* High Contrast */}
          <div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Contrast className="h-4 w-4 text-orange-400" aria-hidden="true" />
                <label htmlFor="high-contrast-toggle" className="text-sm font-medium text-white">
                  High Contrast Mode
                </label>
              </div>
              <button
                id="high-contrast-toggle"
                onClick={handleHighContrastToggle}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  isHighContrast
                    ? 'bg-orange-500'
                    : 'bg-white/20'
                }`}
                role="switch"
                aria-checked={isHighContrast}
                aria-label={`${isHighContrast ? 'Disable' : 'Enable'} high contrast mode`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    isHighContrast ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
            <p className="text-xs text-gray-400 mt-1">
              Increases contrast for better visibility
            </p>
          </div>

          {/* Keyboard Shortcuts Info */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Eye className="h-4 w-4 text-orange-400" aria-hidden="true" />
              <h3 className="text-sm font-medium text-white">
                Keyboard Shortcuts
              </h3>
            </div>
            <div className="space-y-2 text-xs text-gray-300">
              <div className="flex justify-between">
                <span>Toggle microphone:</span>
                <kbd className="px-2 py-1 bg-white/10 rounded text-white">M</kbd>
              </div>
              <div className="flex justify-between">
                <span>Toggle camera:</span>
                <kbd className="px-2 py-1 bg-white/10 rounded text-white">V</kbd>
              </div>
              <div className="flex justify-between">
                <span>Open settings:</span>
                <kbd className="px-2 py-1 bg-white/10 rounded text-white">S</kbd>
              </div>
              <div className="flex justify-between">
                <span>Leave meeting:</span>
                <kbd className="px-2 py-1 bg-white/10 rounded text-white">Esc</kbd>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-6 pt-4 border-t border-white/10">
          <button
            onClick={onClose}
            className="w-full bg-orange-500 hover:bg-orange-600 px-4 py-2 rounded-lg text-white transition-colors"
          >
            Save Settings
          </button>
        </div>
      </div>
    </div>
  );
};