/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/static/**/*.html'],
  theme: {
    extend: {
      colors: {
        bg:      '#0f1117',
        surface: '#1a1d27',
        border:  '#2a2d3a',
        accent:  '#6c8cf5',
        accent2: '#a78bfa',
        text:    '#e2e4ed',
        muted:   '#6b7280',
        success: '#34d399',
        danger:  '#f87171',
      },
    },
  },
  plugins: [],
}
