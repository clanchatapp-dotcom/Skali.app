/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
      colors: {
        ink: 'rgb(var(--ink) / <alpha-value>)',
        panel: 'rgb(var(--panel) / <alpha-value>)',
        panel2: 'rgb(var(--panel2) / <alpha-value>)',
        edge: 'rgb(var(--edge) / <alpha-value>)',
        brand: {
          DEFAULT: 'rgb(var(--brand) / <alpha-value>)',
          600: 'rgb(var(--brand-600) / <alpha-value>)',
          700: 'rgb(var(--brand-700) / <alpha-value>)',
        },
      },
      keyframes: {
        pop: { '0%': { transform: 'translateY(4px) scale(.98)', opacity: '0' }, '100%': { transform: 'translateY(0) scale(1)', opacity: '1' } },
      },
      animation: { pop: 'pop .18s ease-out' },
    },
  },
  plugins: [],
}
