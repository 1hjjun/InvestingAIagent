/** @type {import('tailwindcss').Config} */
const config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#141821",
        mist: "#f5f7fa",
        line: "#e2e7ee",
        pine: "#2563eb",
        coral: "#df6757",
        amber: "#f59e0b",
      },
      boxShadow: {
        soft: "0 18px 48px rgba(20, 24, 33, 0.08)",
      },
    },
  },
  plugins: [],
};

module.exports = config;
