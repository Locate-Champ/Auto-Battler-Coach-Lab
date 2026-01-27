/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bg-primary': '#030712',
        'bg-secondary': '#111827',
        'bg-card': '#1f2937',
        'bg-hover': '#374151',
        'cyan-primary': '#00d4ff',
        'cyan-muted': '#0891b2',
        'cost-1': '#6b7280',
        'cost-2': '#22c55e',
        'cost-3': '#3b82f6',
        'cost-4': '#a855f7',
        'cost-5': '#eab308',
      },
      fontFamily: {
        'sans': ['Inter', '-apple-system', 'BlinkMacSystemFont', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
