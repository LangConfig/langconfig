/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

export type ThemeName = 'langconfig' | 'dark' | 'light' | 'midnight' | 'ocean' | 'forest' | 'botanical' | 'godspeed' | 'cream' | 'cream-peach';

export interface Theme {
  name: ThemeName;
  displayName: string;
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
  textured?: boolean;
}

export const themes: Record<ThemeName, Theme> = {
  langconfig: {
    name: 'langconfig',
    displayName: 'LangConfig (Signature)',
    colors: {
      primary: '#2E5C8A',
      backgroundLight: '#F5F9FC',
      backgroundDark: '#D8EDF5',
      panelDark: '#E3F0F5',
      borderDark: '#2E5C8A',
      textMuted: '#4A6B8A',
      textPrimary: '#1a2332',
      inputBackground: '#FFFFFF',
      logoBackground: '#FFFFFF',
      nodeBackground: '#6B9E7E',
      nodeBackgroundLight: '#8AB5A0',
      categoryBackground: '#C5E0E5',
    },
    textured: true,
  },
  dark: {
    name: 'dark',
    displayName: 'Dark Blue',
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

export function applyTheme(theme: Theme) {
  const root = document.documentElement;

  // Set CSS variables
  root.style.setProperty('--color-primary', theme.colors.primary);
  root.style.setProperty('--color-background-light', theme.colors.backgroundLight);
  root.style.setProperty('--color-background-dark', theme.colors.backgroundDark);
  root.style.setProperty('--color-panel-dark', theme.colors.panelDark);
  root.style.setProperty('--color-border-dark', theme.colors.borderDark);
  root.style.setProperty('--color-text-muted', theme.colors.textMuted);
  root.style.setProperty('--color-text-primary', theme.colors.textPrimary);
  root.style.setProperty('--color-input-background', theme.colors.inputBackground);
  root.style.setProperty('--color-logo-background', theme.colors.logoBackground);
  root.style.setProperty('--color-node-background', theme.colors.nodeBackground);
  root.style.setProperty('--color-node-background-light', theme.colors.nodeBackgroundLight);
  root.style.setProperty('--color-category-background', theme.colors.categoryBackground);

  // Set data-theme attribute for CSS targeting
  root.setAttribute('data-theme', theme.name);

  // Add/remove textured class
  if (theme.textured) {
    root.classList.add('textured-theme');
  } else {
    root.classList.remove('textured-theme');
  }

  // Save to localStorage
  localStorage.setItem('langconfig-theme', theme.name);
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
