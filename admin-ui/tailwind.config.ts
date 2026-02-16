import type { Config } from "tailwindcss";

export default {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/contexts/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  safelist: [
    'animate-slide-in-right',
    'bg-white',
    'border-green-200',
    'border-red-200',
    'border-blue-200',
    'border-yellow-200',
    'text-green-500',
    'text-red-500',
    'text-blue-500',
    'text-yellow-500',
  ],
  theme: {
    extend: {
      keyframes: {
        'slide-in-right': {
          'from': {
            transform: 'translateX(100%)',
            opacity: '0',
          },
          'to': {
            transform: 'translateX(0)',
            opacity: '1',
          },
        },
      },
      animation: {
        'slide-in-right': 'slide-in-right 0.3s ease-out',
      },
    },
  },
  plugins: [],
} satisfies Config;

