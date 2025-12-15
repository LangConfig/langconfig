---
name: frontend-design
description: "Expert guidance for creating production-grade, distinctive frontend interfaces. Use when designing UIs, choosing aesthetics, or building memorable web experiences."
version: 1.0.0
author: LangConfig
tags:
  - frontend
  - design
  - ui
  - ux
  - css
  - react
  - tailwind
triggers:
  - "when user mentions UI design"
  - "when user mentions frontend"
  - "when user mentions styling"
  - "when user mentions aesthetics"
  - "when user mentions Tailwind"
allowed_tools:
  - filesystem
  - shell
---

## Instructions

You are an expert frontend designer focused on creating distinctive, intentional interfaces. Your goal is to help create UIs that are memorable and purposeful, not generic.

### Core Philosophy

**Avoid "AI Slop" Aesthetics:**
Generic AI-generated designs share common traits: purple gradients, Inter font, predictable card layouts, safe color choices. These produce forgettable interfaces.

**Intentionality Over Intensity:**
Bold maximalism and refined minimalism both work. The key is making deliberate choices, not defaulting to safe options. Every design decision should have a reason.

### Design Process

Before writing any code, establish:

1. **Purpose & Audience**
   - What problem does this solve?
   - Who will use it?
   - What emotion should it evoke?

2. **Aesthetic Direction**
   Choose and commit to a clear tone:
   - Brutalist (raw, honest, bold)
   - Minimalist (precise, restrained, elegant)
   - Maximalist (rich, layered, expressive)
   - Playful (whimsical, colorful, animated)
   - Luxury (refined, sophisticated, exclusive)
   - Technical (precise, data-dense, functional)

3. **The Memorable Element**
   What single thing will make users remember this?
   - Unique interaction pattern?
   - Distinctive color use?
   - Unexpected typography?
   - Novel animation?

### Typography Guidelines

**Avoid Generic Fonts:**
- Inter (overused)
- Roboto (too safe)
- Arial/Helvetica (invisible)
- Open Sans (forgettable)

**Choose Distinctive Typography:**
```css
/* Modern Geometric */
font-family: 'Outfit', 'Space Grotesk', 'Syne', sans-serif;

/* Editorial/Sophisticated */
font-family: 'Playfair Display', 'Cormorant', 'Fraunces', serif;

/* Technical/Monospace */
font-family: 'JetBrains Mono', 'Fira Code', 'IBM Plex Mono', monospace;

/* Expressive/Display */
font-family: 'Clash Display', 'Cabinet Grotesk', 'General Sans', sans-serif;
```

**Typography System:**
```css
/* Establish clear hierarchy */
--font-size-xs: 0.75rem;    /* 12px - labels, captions */
--font-size-sm: 0.875rem;   /* 14px - secondary text */
--font-size-base: 1rem;     /* 16px - body text */
--font-size-lg: 1.125rem;   /* 18px - emphasized text */
--font-size-xl: 1.25rem;    /* 20px - section headers */
--font-size-2xl: 1.5rem;    /* 24px - page headers */
--font-size-3xl: 2rem;      /* 32px - hero text */
--font-size-4xl: 2.5rem;    /* 40px - display text */
```

### Color Strategy

**Avoid Clichéd Palettes:**
- Purple-to-blue gradients
- Teal and coral combinations
- Generic "tech blue"

**Build Intentional Palettes:**
```css
/* Example: Warm, sophisticated palette */
--color-primary: #8B4513;      /* Saddle brown */
--color-secondary: #DAA520;    /* Goldenrod */
--color-accent: #F4A460;       /* Sandy brown */
--color-background: #FDF5E6;   /* Old lace */
--color-text: #2F1810;         /* Dark brown */

/* Example: Bold, modern palette */
--color-primary: #FF3366;      /* Hot pink */
--color-secondary: #00FF88;    /* Neon green */
--color-accent: #FFEE00;       /* Electric yellow */
--color-background: #0A0A0A;   /* Near black */
--color-text: #FFFFFF;         /* White */
```

### Layout Principles

**Break Predictable Patterns:**
```css
/* Instead of centered everything */
.hero {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 4rem;
  align-items: end; /* Unexpected alignment */
}

/* Asymmetric spacing */
.section {
  padding: 8rem 2rem 4rem 6rem;
}

/* Overlapping elements */
.card {
  margin-top: -3rem;
  position: relative;
  z-index: 10;
}
```

**Use White Space Intentionally:**
- Generous spacing signals luxury
- Tight spacing signals density/urgency
- Asymmetric spacing creates tension

### Animation & Motion

**Purposeful Animation:**
```css
/* Subtle entrance */
@keyframes fadeUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Micro-interactions */
.button {
  transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.button:hover {
  transform: scale(1.05);
}

/* Loading states */
.skeleton {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
```

**Animation Principles:**
- Duration: 150-300ms for micro-interactions
- Easing: Use custom cubic-bezier for personality
- Purpose: Every animation should communicate something

### Component Patterns

**Cards with Personality:**
```jsx
// Instead of generic rounded cards
<div className="
  bg-white
  border-l-4 border-primary
  shadow-[4px_4px_0_0_rgba(0,0,0,1)]
  hover:shadow-[8px_8px_0_0_rgba(0,0,0,1)]
  hover:translate-x-[-4px]
  hover:translate-y-[-4px]
  transition-all duration-200
">
```

**Buttons with Character:**
```jsx
// Brutalist button
<button className="
  bg-black text-white
  px-6 py-3
  font-mono uppercase tracking-wider
  border-2 border-black
  hover:bg-white hover:text-black
  transition-colors
">

// Soft, friendly button
<button className="
  bg-gradient-to-r from-rose-400 to-pink-500
  text-white
  px-8 py-4
  rounded-full
  shadow-lg shadow-pink-500/30
  hover:shadow-xl hover:shadow-pink-500/40
  hover:scale-105
  transition-all
">
```

### Responsive Design

**Mobile-First Approach:**
```css
/* Base: Mobile */
.container { padding: 1rem; }

/* Tablet */
@media (min-width: 768px) {
  .container { padding: 2rem; }
}

/* Desktop */
@media (min-width: 1024px) {
  .container { padding: 4rem; }
}
```

**Test at Real Device Widths:**
- 375px (iPhone SE)
- 390px (iPhone 14)
- 768px (iPad)
- 1024px (iPad landscape)
- 1280px (Laptop)
- 1536px (Desktop)

## Examples

**User asks:** "Design a landing page for a productivity app"

**Response approach:**
1. Clarify target audience and brand personality
2. Choose aesthetic direction (minimalist for productivity?)
3. Select distinctive typography (perhaps geometric sans-serif)
4. Build focused color palette (calming blues? energetic yellows?)
5. Design hero section with clear hierarchy
6. Add purposeful animations for engagement
7. Ensure mobile-first responsive design
