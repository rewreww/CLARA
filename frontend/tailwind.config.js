/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#060b14',
        panel: '#0a1220',
        card: '#0d1526',
        border: '#1a2d4e',
        accent: '#2563eb',
        accent2: '#0ea5e9',
        muted: '#6b7f99',
        success: '#10b981',
        warning: '#f59e0b',
        danger: '#ef4444',
      },
    },
  },
  plugins: [],
};
