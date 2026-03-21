/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/static/**/*.html'],
  safelist: [
    // JS-generated classes that use dynamic string concatenation
    'group-hover:opacity-100',
    'border-accent',
    'bg-[#0d2e22]', 'bg-[#2e0d0d]',
    'bg-[#1a2e1a]', 'bg-[#1a1e2e]',
    'bg-[#1a0a0a]', 'border-[#2e1010]', 'border-[#1e2030]',
    'text-[#fbbf24]',
  ],
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
