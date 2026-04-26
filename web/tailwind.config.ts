import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './features/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}'
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f5f3ff',
          100: '#ede9fe',
          200: '#ddd6fe',
          300: '#c4b5fd',
          400: '#a78bfa',
          500: '#7c3aed',
          600: '#6d28d9',
          700: '#5b21b6',
          800: '#4c1d95',
          950: '#2e1065',
        }
      },
      boxShadow: {
        panel: '0 12px 36px rgba(15, 23, 42, 0.08)',
        fintech: '0 4px 24px -4px rgba(15, 23, 42, 0.04)',
        'fintech-sm': '0 2px 8px -2px rgba(15, 23, 42, 0.04)'
      }
    }
  },
  plugins: [require('@tailwindcss/typography')]
};

export default config;
