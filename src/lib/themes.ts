/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

export type ThemeName =
  | 'langconfig'
  | 'nightbloom'
  | 'dark'
  | 'light'
  | 'midnight'
  | 'ocean'
  | 'forest'
  | 'botanical'
  | 'godspeed'
  | 'cream'
  | 'cream-peach';

export interface Theme {
  name: ThemeName;
  displayName: string;
  /**
   * Canonical expression mode. Light themes use brutalist offset shadows and
   * tight radii; dark themes swap to glows and relaxed radii per the
   * Botanical Brutalism dark variant ("nighttime garden").
   */
  mode: 'light' | 'dark';
  colors: {
    primary: string;
    backgroundLight: string;
    backgroundDark: string;
    panelDark: string;
    borderDark: string;
    textMuted: string;
    textPrimary: string;
    inputBackground: string;
    logoBackground: string;
    nodeBackground: string;
    nodeBackgroundLight: string;
    categoryBackground: string;
  };
  /**
   * Optional hand-tuned overrides for the extended token set. Anything not
   * provided is derived from `mode` + base colors by resolveTokens().
   */
  extended?: Partial<ExtendedTokens>;
  textured?: boolean;
}

export interface ExtendedTokens {
  success: string;
  warning: string;
  error: string;
  info: string;
  onAccent: string;
  surface0: string;
  surface1: string;
  surface2: string;
  surfaceTerminal: string;
  borderStrong: string;
  borderSubtle: string;
  shadowCard: string;
  shadowCardSm: string;
  shadowPressed: string;
  glowAccent: string;
  radiusCard: string;
  radiusControl: string;
  borderW: string;
  pressShift: string;
  atmosphere: string;
}

export const themes: Record<ThemeName, Theme> = {
  langconfig: {
    name: 'langconfig',
    displayName: 'LangConfig Peony',
    mode: 'light',
    colors: {
      primary: '#D98984',
      backgroundLight: '#FFF8ED',
      backgroundDark: '#F8E7DC',
      panelDark: '#F6D4CF',
      borderDark: '#102D43',
      textMuted: '#7B6870',
      textPrimary: '#12283B',
      inputBackground: '#FFFCF6',
      logoBackground: '#FFF8ED',
      nodeBackground: '#E8B2AD',
      nodeBackgroundLight: '#F5D5D0',
      categoryBackground: '#F0C5BE',
    },
    extended: {
      success: '#3E7C4F',
      warning: '#B07D2B',
      error: '#B6463F',
      info: '#3A6B8A',
      onAccent: '#FFFFFF',
    },
    textured: true,
  },
  nightbloom: {
    name: 'nightbloom',
    displayName: 'Nightbloom',
    mode: 'dark',
    colors: {
      primary: '#E8A09A', // desaturated glowing peony rose
      backgroundLight: '#121018', // page — rich soil, warm violet-black
      backgroundDark: '#1A1A2E',
      panelDark: '#1B1926',
      borderDark: 'rgba(255, 255, 255, 0.12)',
      textMuted: '#9A8FA3', // dusty mauve
      textPrimary: '#ECE6DA', // warm parchment
      inputBackground: '#0A0A0B',
      logoBackground: '#1B1926',
      nodeBackground: '#221E30',
      nodeBackgroundLight: '#2B2640',
      categoryBackground: '#251F35',
    },
    extended: {
      success: '#8FD4A8',
      warning: '#E6C47F',
      error: '#E89A9A',
      info: '#9AB8E8',
      onAccent: '#1A0F12',
      surface0: '#121018',
      surface1: '#1B1926',
      surface2: '#241F31',
      shadowCard:
        '0 0 0 1px rgba(232, 160, 154, 0.06), 0 8px 32px rgba(0, 0, 0, 0.45), 0 0 18px rgba(232, 160, 154, 0.06)',
      glowAccent: '0 0 20px rgba(232, 160, 154, 0.30)',
      atmosphere:
        'radial-gradient(ellipse at 50% 30%, rgba(36, 28, 54, 0.55) 0%, rgba(10, 10, 11, 0.92) 100%)',
    },
  },
  dark: {
    name: 'dark',
    displayName: 'Dark Blue',
    mode: 'dark',
    colors: {
      primary: '#135bec',
      backgroundLight: '#f6f6f8',
      backgroundDark: '#101622',
      panelDark: '#181e29',
      borderDark: '#232f48',
      textMuted: '#92a4c9',
      textPrimary: '#e5e9f0',
      inputBackground: '#0c1018',
      logoBackground: '#1a2332', // Slightly lighter than panel for contrast
      nodeBackground: '#181e29',
      nodeBackgroundLight: '#232f48',
      categoryBackground: '#1a2332',
    },
  },
  light: {
    name: 'light',
    displayName: 'Light',
    mode: 'light',
    colors: {
      primary: '#2563eb',
      backgroundLight: '#ffffff',
      backgroundDark: '#f8fafc',
      panelDark: '#f1f5f9',
      borderDark: '#e2e8f0',
      textMuted: '#64748b',
      textPrimary: '#1e293b',
      inputBackground: '#ffffff',
      logoBackground: '#ffffff', // White for clean look
      nodeBackground: '#f1f5f9',
      nodeBackgroundLight: '#e2e8f0',
      categoryBackground: '#e2e8f0',
    },
  },
  midnight: {
    name: 'midnight',
    displayName: 'Midnight',
    mode: 'dark',
    colors: {
      primary: '#8b5cf6',
      backgroundLight: '#fafafa',
      backgroundDark: '#0a0a0a',
      panelDark: '#141414',
      borderDark: '#262626',
      textMuted: '#a3a3a3',
      textPrimary: '#f5f5f5',
      inputBackground: '#050505',
      logoBackground: '#1a1a1a', // Slightly lighter than background
      nodeBackground: '#141414',
      nodeBackgroundLight: '#262626',
      categoryBackground: '#1a1a1a',
    },
  },
  ocean: {
    name: 'ocean',
    displayName: 'Ocean',
    mode: 'dark',
    colors: {
      primary: '#06b6d4',
      backgroundLight: '#f0fdfa',
      backgroundDark: '#042f2e',
      panelDark: '#134e4a',
      borderDark: '#FF8559',
      textMuted: '#5FB9B0',
      textPrimary: '#ecfeff',
      inputBackground: '#022020',
      logoBackground: '#0a3a38', // Teal that contrasts with turquoise header
      nodeBackground: '#134e4a',
      nodeBackgroundLight: '#0f6b66',
      categoryBackground: '#0a4a46',
    },
  },
  forest: {
    name: 'forest',
    displayName: 'Forest',
    mode: 'dark',
    colors: {
      primary: '#10b981',
      backgroundLight: '#f0fdf4',
      backgroundDark: '#022c22',
      panelDark: '#064e3b',
      borderDark: '#5B9BD5',
      textMuted: '#6DB893',
      textPrimary: '#d1fae5',
      inputBackground: '#011a15',
      logoBackground: '#083d2e', // Dark forest green that works with emerald header
      nodeBackground: '#064e3b',
      nodeBackgroundLight: '#0a6b4a',
      categoryBackground: '#083d2e',
    },
  },
  botanical: {
    name: 'botanical',
    displayName: 'Botanical',
    mode: 'light',
    colors: {
      primary: '#2D7A5E',
      backgroundLight: '#F5F3E8',
      backgroundDark: '#1E3A2C',
      panelDark: '#2A5040',
      borderDark: '#C17455',
      textMuted: '#A8B99C',
      textPrimary: '#F5F3E8',
      inputBackground: '#152820',
      logoBackground: '#1E3A2C', // Match background for subtle look
      nodeBackground: '#2A5040',
      nodeBackgroundLight: '#3a6450',
      categoryBackground: '#254838',
    },
  },
  godspeed: {
    name: 'godspeed',
    displayName: 'Godspeed',
    mode: 'light',
    colors: {
      primary: '#92B4C8',
      backgroundLight: '#F5E9D3',
      backgroundDark: '#4A4035',
      panelDark: '#5A5045',
      borderDark: '#B8A89A',
      textMuted: '#A8C4D8',
      textPrimary: '#F5E9D3',
      inputBackground: '#3a3028',
      logoBackground: '#635850', // Warm medium brown that contrasts with powder blue
      nodeBackground: '#5A5045',
      nodeBackgroundLight: '#6a6055',
      categoryBackground: '#544a40',
    },
  },
  cream: {
    name: 'cream',
    displayName: 'Cream',
    mode: 'light',
    colors: {
      primary: '#2E5C8A', // Keep blue primary
      backgroundLight: '#FDF8F3', // Warm cream background
      backgroundDark: '#F5EFE7', // Slightly darker cream
      panelDark: '#FEFAF5', // Light cream panels
      borderDark: '#E8DCC8', // Warm taupe borders
      textMuted: '#8B7D6B', // Warm brown muted text
      textPrimary: '#2D2416', // Dark warm text
      inputBackground: '#FFFFFF', // White inputs
      logoBackground: '#FFFFFF', // White for clean contrast
      nodeBackground: '#F5EFE7',
      nodeBackgroundLight: '#E8DCC8',
      categoryBackground: '#2E5C8A', // Use primary color (blue)
    },
  },
  'cream-peach': {
    name: 'cream-peach',
    displayName: 'Cream (Peach)',
    mode: 'light',
    colors: {
      primary: '#2E5C8A', // Keep blue primary
      backgroundLight: '#FDF8F3', // Warm cream background
      backgroundDark: '#F5EFE7', // Slightly darker cream
      panelDark: '#FEFAF5', // Light cream panels
      borderDark: '#E8DCC8', // Warm taupe borders
      textMuted: '#8B7D6B', // Warm brown muted text
      textPrimary: '#2D2416', // Dark warm text
      inputBackground: '#FFFFFF', // White inputs
      logoBackground: '#FFFFFF', // White for clean contrast
      nodeBackground: '#F5EFE7',
      nodeBackgroundLight: '#E8DCC8',
      categoryBackground: '#E8B896', // Peachy-terracotta accent for categories
    },
  },
};

/** Relative luminance check to pick readable text on the accent color. */
function isLightColor(hex: string): boolean {
  const m = hex.replace('#', '');
  if (m.length < 6) return false;
  const r = parseInt(m.slice(0, 2), 16);
  const g = parseInt(m.slice(2, 4), 16);
  const b = parseInt(m.slice(4, 6), 16);
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.62;
}

/**
 * Resolve the full extended token set for a theme. Hand-tuned themes
 * (peony, nightbloom) override via `extended`; the legacy themes get
 * sensible defaults derived from their mode and base palette.
 */
export function resolveTokens(theme: Theme): Record<string, string> {
  const { colors, mode } = theme;
  const dark = mode === 'dark';
  const accent = colors.primary;

  const defaults: ExtendedTokens = {
    success: dark ? '#8FD4A8' : '#3E7C4F',
    warning: dark ? '#E6C47F' : '#B07D2B',
    error: dark ? '#E89A9A' : '#B6463F',
    info: dark ? '#9AB8E8' : '#3A6B8A',
    onAccent: isLightColor(accent) ? '#1A1A22' : '#FFFFFF',
    surface0: dark ? colors.backgroundDark : colors.backgroundLight,
    surface1: dark ? colors.panelDark : '#FFFFFF',
    surface2: dark ? colors.nodeBackgroundLight : colors.backgroundDark,
    surfaceTerminal: dark ? '#0A0A0B' : '#1E1E1E',
    borderStrong: dark ? 'rgba(255, 255, 255, 0.12)' : colors.borderDark,
    borderSubtle: dark
      ? 'rgba(255, 255, 255, 0.07)'
      : `color-mix(in srgb, ${colors.borderDark} 30%, transparent)`,
    shadowCard: dark
      ? `0 0 0 1px color-mix(in srgb, ${accent} 6%, transparent), 0 8px 32px rgba(0, 0, 0, 0.45)`
      : `4px 4px 0 ${colors.borderDark}`,
    shadowCardSm: dark
      ? `0 0 0 1px color-mix(in srgb, ${accent} 6%, transparent), 0 4px 16px rgba(0, 0, 0, 0.40)`
      : `2px 2px 0 ${colors.borderDark}`,
    shadowPressed: dark
      ? `0 0 0 1px color-mix(in srgb, ${accent} 10%, transparent), 0 2px 8px rgba(0, 0, 0, 0.35)`
      : `1px 1px 0 ${colors.borderDark}`,
    glowAccent: dark
      ? `0 0 20px color-mix(in srgb, ${accent} 30%, transparent)`
      : '0 0 0 0 transparent',
    radiusCard: dark ? '12px' : '4px',
    radiusControl: dark ? '8px' : '4px',
    borderW: dark ? '1px' : '2px',
    pressShift: dark ? '1px' : '2px',
    atmosphere: 'none',
  };

  const ext: ExtendedTokens = { ...defaults, ...theme.extended };

  const wash = (c: string, pct: number) => `color-mix(in srgb, ${c} ${pct}%, transparent)`;
  const tones = { success: ext.success, warning: ext.warning, error: ext.error, info: ext.info };

  const tokens: Record<string, string> = {
    // Base palette (legacy 12)
    '--color-primary': colors.primary,
    '--color-background-light': colors.backgroundLight,
    '--color-background-dark': colors.backgroundDark,
    '--color-panel-dark': colors.panelDark,
    '--color-border-dark': colors.borderDark,
    '--color-text-muted': colors.textMuted,
    '--color-text-primary': colors.textPrimary,
    '--color-input-background': colors.inputBackground,
    '--color-logo-background': colors.logoBackground,
    '--color-node-background': colors.nodeBackground,
    '--color-node-background-light': colors.nodeBackgroundLight,
    '--color-category-background': colors.categoryBackground,

    // Semantic status tones
    '--color-success': tones.success,
    '--color-warning': tones.warning,
    '--color-error': tones.error,
    '--color-info': tones.info,
    '--color-on-accent': ext.onAccent,

    // Surfaces & borders
    '--surface-0': ext.surface0,
    '--surface-1': ext.surface1,
    '--surface-2': ext.surface2,
    '--surface-terminal': ext.surfaceTerminal,
    '--border-strong': ext.borderStrong,
    '--border-subtle': ext.borderSubtle,

    // Theme-switched geometry: offset shadows in light, glows in dark.
    '--shadow-card': ext.shadowCard,
    '--shadow-card-sm': ext.shadowCardSm,
    '--shadow-pressed': ext.shadowPressed,
    '--glow-accent': ext.glowAccent,
    '--radius-card': ext.radiusCard,
    '--radius-control': ext.radiusControl,
    '--border-w': ext.borderW,
    '--press-shift': ext.pressShift,
    '--atmosphere': ext.atmosphere,

    // Accent wash for badges/hover fills
    '--color-accent-wash': wash(accent, dark ? 16 : 12),
  };

  for (const [tone, color] of Object.entries(tones)) {
    tokens[`--color-${tone}-wash`] = wash(color, dark ? 14 : 11);
    tokens[`--color-${tone}-border`] = wash(color, dark ? 30 : 45);
    tokens[`--glow-${tone}`] = dark ? `0 0 16px ${wash(color, 35)}` : '0 0 0 0 transparent';
  }

  return tokens;
}

export function applyTheme(theme: Theme) {
  const root = document.documentElement;

  const tokens = resolveTokens(theme);
  for (const [name, value] of Object.entries(tokens)) {
    root.style.setProperty(name, value);
  }

  // Set data-theme attribute for CSS targeting
  root.setAttribute('data-theme', theme.name);

  // Toggle Tailwind dark variants so dark: utilities match the active theme.
  if (theme.mode === 'dark') {
    root.classList.add('dark');
  } else {
    root.classList.remove('dark');
  }

  // Add/remove textured class
  if (theme.textured) {
    root.classList.add('textured-theme');
  } else {
    root.classList.remove('textured-theme');
  }

  // Save to localStorage
  localStorage.setItem('langconfig-theme', theme.name);

  // Notify theme-reactive consumers outside the CSS cascade (e.g. canvas/3D materials)
  window.dispatchEvent(new CustomEvent('langconfig:theme-changed', { detail: { theme: theme.name, mode: theme.mode } }));
}

export function loadTheme(): Theme {
  const savedTheme = localStorage.getItem('langconfig-theme') as ThemeName;
  return themes[savedTheme] || themes.langconfig;
}

export function initializeTheme() {
  const theme = loadTheme();
  applyTheme(theme);
  return theme;
}
