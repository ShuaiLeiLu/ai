import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './features/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}'
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          'var(--font-inter)',
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          '"PingFang SC"',
          '"HarmonyOS Sans SC"',
          '"Microsoft YaHei"',
          '"Hiragino Sans GB"',
          'sans-serif'
        ],
        serif: [
          'var(--font-serif-sc)',
          '"Noto Serif SC"',
          '"STSong"',
          '"SimSun"',
          'serif'
        ]
      },
      colors: {
        // 宣纸 → 玄黑：温润中性
        ink: {
          0: '#fbfaf7',
          25: '#f5f3ee',
          50: '#ece9e1',
          100: '#d9d4c8',
          200: '#b8b0a0',
          300: '#9a907d',
          400: '#7a7264',
          500: '#5d564b',
          600: '#4a443a',
          700: '#34302a',
          800: '#2a2620',
          900: '#171410'
        },
        // 松烟墨：品牌主色
        brand: {
          50: '#e9f1ec',
          100: '#c9dfd0',
          200: '#a4c9b1',
          300: '#6e9d83',
          400: '#48825f',
          500: '#2e6e51',
          600: '#1d4a34',
          700: '#143929',
          800: '#0f2a1e',
          900: '#0a1f18',
          950: '#061310'
        },
        // 朱砂红：A 股「涨」
        up: {
          50: '#fdecec',
          100: '#fbd3d0',
          200: '#f5a8a1',
          300: '#ec7f74',
          400: '#e25c4f',
          500: '#d8453a',
          600: '#c0362c',
          700: '#9c2a23'
        },
        // 青翠：A 股「跌」
        down: {
          50: '#e8f3ec',
          100: '#c6e1d0',
          200: '#94c8a8',
          300: '#62af80',
          400: '#3f9a67',
          500: '#2f9e60',
          600: '#1f7f4a',
          700: '#175f37'
        },
        // 神州金：稀缺强调
        gold: {
          50: '#fdf7e6',
          100: '#fdf4d8',
          200: '#f5e6b3',
          300: '#ecd58a',
          400: '#d7ad55',
          500: '#c89a3a',
          600: '#9f7a2a',
          700: '#7a5d20'
        }
      },
      boxShadow: {
        card: '0 1px 2px rgba(23,20,16,.04), 0 1px 1px rgba(23,20,16,.03)',
        'card-md': '0 2px 8px rgba(23,20,16,.05), 0 1px 2px rgba(23,20,16,.04)',
        'card-lg': '0 8px 28px rgba(23,20,16,.08), 0 2px 6px rgba(23,20,16,.04)',
        brand: '0 4px 12px rgba(29,74,52,.22)',
        gold: '0 4px 12px rgba(200,154,58,.22)',
        // 兼容旧名
        panel: '0 12px 36px rgba(15, 23, 42, 0.08)',
        fintech: '0 4px 24px -4px rgba(15, 23, 42, 0.04)',
        'fintech-sm': '0 2px 8px -2px rgba(15, 23, 42, 0.04)'
      },
      borderRadius: {
        xl: '14px',
        '2xl': '20px'
      },
      backgroundImage: {
        paper: 'linear-gradient(180deg, #fbfaf7 0%, #f6f3ec 100%)',
        'paper-warm': 'linear-gradient(135deg, #f7f4ec 0%, #ede7d7 100%)',
        'brand-dark': 'linear-gradient(135deg, #1d4a34 0%, #143929 100%)',
        'gold-warm': 'linear-gradient(135deg, #fdf4d8, #f5e6b3)'
      }
    }
  },
  plugins: [require('@tailwindcss/typography')]
};

export default config;
