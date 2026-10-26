/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        brand: {
          50: '#E9F0FF',
          100: '#C8D9FF',
          200: '#A3C0FF',
          300: '#7EA6FF',
          400: '#6293FF',
          500: '#4680FF',
          600: '#3F78FF',
          700: '#376DFF',
          800: '#2F63FF',
          900: '#2050FF',
          950: '#1A3D93',
        },
        canvas: '#F8F9FA',
        surface: '#FFFFFF',
        ink: '#1D2630',
        muted: '#5B6B79',
        line: '#E6EBF1',
        'line-strong': '#DBE0E5',
        success: '#2CA87F',
        warning: '#E58A00',
        danger: '#DC2626',
        info: '#3EC9D6',
      },
      borderRadius: {
        card: '12px',
        control: '8px',
      },
    },
  },
  plugins: [],
};
