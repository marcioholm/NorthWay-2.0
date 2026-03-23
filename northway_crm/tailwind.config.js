module.exports = {
  darkMode: 'class',
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
    './routes/**/*.py'
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        display: ['Outfit', 'sans-serif'],
        dm: ['"DM Sans"', 'sans-serif'],
        serif: ['"DM Serif Display"', 'serif'],
      },
      colors: {
        primary: "#E31E24",
        "background-light": "#F8F9FA",
        "background-dark": "#0D0F12",
        "sidebar-dark": "#090A0C",
        "card-dark": "#1A1D23",
        "board-dark": "#121418",
        northway: {
          red: '#fa0102',
          orange: '#fe422e',
          dark: '#0f0518',
          gray: '#f3f4f6',
          light: '#fdfdfd',
          paper: '#ffffff',
          subtle: '#f8fafc'
        }
      },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(31, 38, 135, 0.07)',
        'glow': '0 0 15px rgba(250, 1, 2, 0.3)',
      },
      borderRadius: {
        DEFAULT: "0.5rem",
        "xl": "0.75rem",
        "2xl": "1rem",
      },
    }
  },
  plugins: [
    require('@tailwindcss/typography'),
    require('@tailwindcss/forms'),
  ],
}
