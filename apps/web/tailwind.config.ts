import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: "#0f1f3d",
        ink: "#26324a",
        accent: "#d92f8a",
        blush: "#fff1f8",
        mist: "#f6f8fb"
      },
      boxShadow: {
        soft: "0 14px 40px rgba(15,31,61,0.08)"
      }
    }
  },
  plugins: []
};

export default config;
