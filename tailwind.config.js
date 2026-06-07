/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/templates/**/*.html.j2", "./app/static/**/*.js"],
  theme: {
    extend: {},
  },
  plugins: [require("flowbite-typography")],
};
