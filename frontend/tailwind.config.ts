import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172033",
        muted: "#667085",
        panel: "#f8fafc",
        brand: "#2563eb",
      },
    },
  },
  plugins: [],
};

export default config;
