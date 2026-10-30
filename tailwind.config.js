/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './profile_post/templates/**/*.html',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'Segoe UI', 'Arial', 'sans-serif'],
      },
      colors: {
        brand: {
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          800: '#166534',
          900: '#14532d',
        },
        repair: {
          mintLight: '#F4FBF7',
          mintSoft: '#E3F4EA',
          mintMid: '#88E2A6',
          leaf: '#288B48',
          vibrant: '#109E48',
          forest: '#0D5C31',
          amber: '#B98B22',
          gold: '#F5D000',
        },
      },
    },
  },
  plugins: [],
};
