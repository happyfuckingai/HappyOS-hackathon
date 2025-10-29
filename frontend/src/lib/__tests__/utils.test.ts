import { cn } from '../utils';

describe('Utils', () => {
  describe('cn (className utility)', () => {
    it('should merge class names correctly', () => {
      const result = cn('base-class', 'additional-class');
      expect(result).toBe('base-class additional-class');
    });

    it('should handle conditional classes', () => {
      const result = cn('base-class', true && 'conditional-class', false && 'hidden-class');
      expect(result).toBe('base-class conditional-class');
    });

    it('should handle undefined and null values', () => {
      const result = cn('base-class', undefined, null, 'valid-class');
      expect(result).toBe('base-class valid-class');
    });

    it('should handle empty strings', () => {
      const result = cn('base-class', '', 'valid-class');
      expect(result).toBe('base-class valid-class');
    });

    it('should handle arrays of classes', () => {
      const result = cn(['class1', 'class2'], 'class3');
      expect(result).toBe('class1 class2 class3');
    });

    it('should handle objects with boolean values', () => {
      const result = cn({
        'active': true,
        'disabled': false,
        'visible': true
      });
      expect(result).toBe('active visible');
    });

    it('should handle complex combinations', () => {
      const isActive = true;
      const isDisabled = false;
      
      const result = cn(
        'base-class',
        {
          'active': isActive,
          'disabled': isDisabled
        },
        isActive && 'state-active',
        ['additional', 'classes']
      );
      
      expect(result).toBe('base-class active state-active additional classes');
    });

    it('should handle Tailwind CSS class conflicts', () => {
      // This tests the tailwind-merge functionality
      const result = cn('px-2 py-1', 'px-4');
      expect(result).toBe('py-1 px-4'); // px-4 should override px-2
    });

    it('should handle responsive classes correctly', () => {
      const result = cn('text-sm', 'md:text-lg', 'lg:text-xl');
      expect(result).toBe('text-sm md:text-lg lg:text-xl');
    });

    it('should handle hover and focus states', () => {
      const result = cn('bg-blue-500', 'hover:bg-blue-600', 'focus:bg-blue-700');
      expect(result).toBe('bg-blue-500 hover:bg-blue-600 focus:bg-blue-700');
    });

    it('should return empty string for no arguments', () => {
      const result = cn();
      expect(result).toBe('');
    });

    it('should handle whitespace correctly', () => {
      const result = cn('  class1  ', '  class2  ');
      expect(result).toBe('class1 class2');
    });
  });
});