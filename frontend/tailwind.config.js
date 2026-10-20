/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#17191c',
        panel: '#1b1e22',
        card: '#202429',
        border: '#33383f',
        accent: '#32b7a5',
        accent2: '#74cfc2',
        muted: '#a0a7af',
        success: '#10b981',
        warning: '#f59e0b',
        danger: '#ef4444',
      },
    },
  },
  plugins: [],
};
