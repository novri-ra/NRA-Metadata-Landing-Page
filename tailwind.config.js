/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Space Grotesk"', 'sans-serif'],
      },
      colors: {
        neon: '#B3FF00',
        base: '#000000',
        surface: '#0D0D0D',
        borderline: '#222222',
        muted: '#888888'
      }
    },
  },
  plugins: [],
}