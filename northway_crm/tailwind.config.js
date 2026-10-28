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
        sans: ['"Plus Jakarta Sans"', 'Inter', 'sans-serif'],
        display: ['"Plus Jakarta Sans"', 'Outfit', 'sans-serif'],
        jakarta: ['"Plus Jakarta Sans"', 'sans-serif'],
        inter: ['Inter', 'sans-serif'],
        outfit: ['Outfit', 'sans-serif'],
        dm: ['"DM Sans"', 'sans-serif'],
        serif: ['"DM Serif Display"', 'serif'],
      },
      colors: {
        nw: {
          canvas: '#E7E9ED',
          shell: '#FBFAF7',
          ink: '#16171A',
          'text-2': '#55575D',
          'text-3': '#45474D',
          border: '#E3E4E8',
          divider: '#DADBDF',
          muted: '#F1EFEA',
          'muted-2': '#EDEBE6',
          hatch: '#D8D6D0',
          accent: '#E31E24',
          'on-accent': '#FFFFFF',
          brand: '#D11A20',
          'status-success': '#1F8A4C',
          'status-info': '#2F6FDB',
          'status-warning': '#B7791F',
          'status-neutral': '#8A8C92',
        },
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
        'nw-shell': '0 30px 60px -32px rgba(20,22,30,.28)',
        'nw-card': '0 4px 20px -4px rgba(20,22,30,.06)',
        'nw-soft': '0 8px 24px -8px rgba(22, 23, 26, 0.08)',
        'glass': '0 8px 32px 0 rgba(31, 38, 135, 0.07)',
        'glow': '0 0 15px rgba(250, 1, 2, 0.3)',
      },
      borderRadius: {
        DEFAULT: "0.5rem",
        "xl": "0.75rem",
        "2xl": "1rem",
        'nw-pill': '999px',
        'nw-card': '20px',
        'nw-card-lg': '24px',
        'nw-panel': '28px',
        'nw-shell': '32px',
        'nw-table': '22px',
        'nw-row': '18px',
        'nw-input': '14px',
      },
    }
  },
  plugins: [
    require('@tailwindcss/typography'),
    require('@tailwindcss/forms'),
  ],
}
