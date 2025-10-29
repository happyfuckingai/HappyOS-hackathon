const defaultTheme = require('tailwindcss/defaultTheme');

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Brand colors based on design system
        brand: {
          blue: '#0A2540',
          orange: '#FF6A3D',
        },
        // Extended blue palette
        blue: {
          50: '#f0f7ff',
          100: '#e0efff',
          200: '#b9dfff',
          300: '#7cc8ff',
          400: '#36b0ff',
          500: '#0c98f1',
          600: '#0078ce',
          700: '#0060a7',
          800: '#05508a',
          900: '#0A2540',
          950: '#0a1829',
        },
        // Extended orange palette
        orange: {
          50: '#fff7ed',
          100: '#ffedd5',
          200: '#fed7aa',
          300: '#fdba74',
          400: '#fb923c',
          500: '#FF6A3D',
          600: '#ea580c',
          700: '#c2410c',
          800: '#9a3412',
          900: '#7c2d12',
          950: '#431407',
        },
        // Glass/glassmorphism colors
        glass: {
          bg: 'rgba(255, 255, 255, 0.05)',
          border: 'rgba(255, 255, 255, 0.1)',
          hover: 'rgba(255, 255, 255, 0.15)',
          active: 'rgba(255, 255, 255, 0.2)',
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'Inter', ...defaultTheme.fontFamily.sans],
        display: ['"Plus Jakarta Sans"', ...defaultTheme.fontFamily.sans],
      },
      fontSize: {
        'display': ['2rem', { lineHeight: '2.5rem', fontWeight: '600' }],
        'title': ['1.5rem', { lineHeight: '2rem', fontWeight: '600' }],
        'heading': ['1.25rem', { lineHeight: '1.75rem', fontWeight: '500' }],
        'body': ['1rem', { lineHeight: '1.5rem', fontWeight: '400' }],
        'small': ['0.875rem', { lineHeight: '1.25rem', fontWeight: '400' }],
        'caption': ['0.75rem', { lineHeight: '1rem', fontWeight: '400' }],
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
      },
      opacity: {
        2: '0.02',
        6: '0.06',
        8: '0.08',
        12: '0.12',
        15: '0.15',
        35: '0.35',
        65: '0.65',
      },
      backdropBlur: {
        '4xl': '60px',
      },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(31, 38, 135, 0.37)',
        'glass-inset': 'inset 0 1px 0 0 rgba(255, 255, 255, 0.12)',
        'glow-orange': '0 20px 45px -15px rgba(255, 106, 61, 0.45)',
        'glow-blue': '0 18px 40px -12px rgba(10, 37, 64, 0.45)',
      },
      backgroundImage: {
        'radial-spark':
          'radial-gradient(120% 120% at 20% 20%, rgba(255,106,61,0.18), transparent 60%), radial-gradient(120% 120% at 80% 0%, rgba(10,37,64,0.22), transparent 65%)',
        'aurora-wash':
          'linear-gradient(130deg, rgba(10, 37, 64, 0.92) 0%, rgba(16, 38, 64, 0.9) 35%, rgba(7, 23, 45, 0.95) 100%)',
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideDown: {
          '0%': { transform: 'translateY(-10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [
    function({ addUtilities }) {
      const newUtilities = {
        '.glass-panel': {
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.37)',
        },
        '.glass-button': {
          backgroundColor: 'rgba(255, 255, 255, 0.1)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.2)',
          transition: 'all 0.2s ease-in-out',
          '&:hover': {
            backgroundColor: 'rgba(255, 255, 255, 0.15)',
          },
          '&:active': {
            backgroundColor: 'rgba(255, 255, 255, 0.2)',
          },
        },
        '.glass-card': {
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '12px',
          boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.37)',
        },
        '.glass-input': {
          backgroundColor: 'rgba(255, 255, 255, 0.08)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.15)',
          '&:focus': {
            backgroundColor: 'rgba(255, 255, 255, 0.12)',
            borderColor: 'rgba(255, 106, 61, 0.5)',
            outline: 'none',
            boxShadow: '0 0 0 2px rgba(255, 106, 61, 0.2)',
          },
        },
      };
      addUtilities(newUtilities);
    },
  ],
};