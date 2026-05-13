/** @type {import('tailwindcss').Config} */
const config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#18202f",
        mist: "#f4f7fb",
        line: "#d9e2ef",
        pine: "#0f766e",
        coral: "#df6757",
        amber: "#d99121",
      },
      boxShadow: {
        soft: "0 18px 60px rgba(24, 32, 47, 0.12)",
      },
    },
  },
  plugins: [],
};

module.exports = config;
