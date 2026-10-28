/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        serif: ["Merriweather", "Georgia", "serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      colors: {
        brand: {
          50: "#f0f4ff",
          100: "#dce8ff",
          200: "#bdd4ff",
          300: "#90b5ff",
          400: "#5e8dff",
          500: "#3b63f7",
          600: "#2545ec",
          700: "#1d34d8",
          800: "#1e2faf",
          900: "#1e2d8a",
          950: "#151d5c",
        },
        slate: {
          850: "#1a2234",
        },
      },
    },
  },
  plugins: [],
};
