/** @type {import(tailwindcss).Config} */
export default {
  content: [
    // Local paths (dev and general usage)
    "./templates/**/*.html",
    "./core/templates/**/*.html",
    "./frontend/**/*.{js,ts}",
    // Absolute paths inside Docker build stage (node-builder at /app)
    "/app/templates/**/*.html",
    "/app/frontend/**/*.{js,ts}",
  ],
  theme: { extend: {} },
  plugins: [],
}
