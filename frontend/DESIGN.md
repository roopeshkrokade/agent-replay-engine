---
name: Agentic Protocol
colors:
  surface: '#10141a'
  surface-dim: '#10141a'
  surface-bright: '#353940'
  surface-container-lowest: '#0a0e14'
  surface-container-low: '#181c22'
  surface-container: '#1c2026'
  surface-container-high: '#262a31'
  surface-container-highest: '#31353c'
  on-surface: '#dfe2eb'
  on-surface-variant: '#e0c0b1'
  inverse-surface: '#dfe2eb'
  inverse-on-surface: '#2d3137'
  outline: '#a78b7d'
  outline-variant: '#584237'
  surface-tint: '#ffb690'
  primary: '#ffb690'
  on-primary: '#552100'
  primary-container: '#f97316'
  on-primary-container: '#582200'
  inverse-primary: '#9d4300'
  secondary: '#bcc7de'
  on-secondary: '#263143'
  secondary-container: '#3e495d'
  on-secondary-container: '#aeb9d0'
  tertiary: '#93ccff'
  on-tertiary: '#003351'
  tertiary-container: '#00a2f4'
  on-tertiary-container: '#003554'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffdbca'
  primary-fixed-dim: '#ffb690'
  on-primary-fixed: '#341100'
  on-primary-fixed-variant: '#783200'
  secondary-fixed: '#d8e3fb'
  secondary-fixed-dim: '#bcc7de'
  on-secondary-fixed: '#111c2d'
  on-secondary-fixed-variant: '#3c475a'
  tertiary-fixed: '#cde5ff'
  tertiary-fixed-dim: '#93ccff'
  on-tertiary-fixed: '#001d32'
  on-tertiary-fixed-variant: '#004b74'
  background: '#10141a'
  on-background: '#dfe2eb'
  surface-variant: '#31353c'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  code-md:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '450'
    lineHeight: 20px
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  container-padding: 1.5rem
  gutter: 1rem
  sidebar-width: 260px
  toolbar-height: 48px
---

## Brand & Style
The design system is engineered for developers and AI engineers who require high-density information visualization without cognitive overload. It prioritizes a **Minimalist-Technical** aesthetic, drawing heavy influence from integrated development environments (IDEs) and precision productivity tools. 

The personality is clinical, efficient, and transparent. It evokes the feeling of a high-performance terminal through a "Code-First" hierarchy where structural chrome recedes to allow agent logs and trace data to take center stage. The visual language utilizes subtle depth and high-contrast typography to ensure clarity in complex debugging workflows.

## Colors
The system utilizes a deep-space palette to reduce eye strain during long debugging sessions. 

- **Primary Canvas**: `#0D1117` serves as the base layer, with surface elevations built using incrementally lighter shades of gray (`#161B22`, `#21262D`).
- **Accents**: The primary orange (`#F97316`) is used sparingly for critical actions and state indicators. 
- **Functional Colors**: Status colors are mapped to semantic meanings. Note that "Warning" and "Divergence" share the primary orange hue to highlight deviation in agent behavior, while "Streaming" utilizes a vibrant Blue to indicate active processing.
- **Borders**: Use low-contrast borders (`#30363D`) to define structure without adding visual noise.

## Typography
This design system employs a dual-font strategy to distinguish between the "Interface" and the "Data."

1.  **Inter (UI Chrome)**: Used for all navigation, headers, button labels, and instructional text. It provides a modern, legible foundation for the application shell.
2.  **JetBrains Mono (Data/Logs)**: Used for agent trace logs, code blocks, JSON payloads, and terminal outputs. The increased x-height and distinct character shapes of JetBrains Mono ensure that complex strings and logic are easily parsable.

**Scaling**: For mobile views, `display-lg` should scale down to `24px` with a `32px` line height to maintain readability within the viewport constraints.

## Layout & Spacing
The layout follows a **Fixed-Viewport Pattern**, common in IDEs, where the main application window does not scroll as a whole. Instead, individual panels (Sidebar, Main Stage, Logs Terminal) have independent scroll containers.

- **Grid**: A fluid 12-column system is used within the "Main Stage" area, while the overall shell is defined by fixed-width sidebars.
- **Rhythm**: A 4px baseline grid governs all spacing. Use `12px` (3 units) for internal component padding and `16px` (4 units) for gap spacing between major layout blocks.
- **Breakpoints**: 
    - *Desktop*: Full 3-column layout (Navigation | Replay Stage | Trace Inspector).
    - *Tablet*: Inspector moves to a collapsible bottom sheet or overlay.
    - *Mobile*: Single column focus; navigation moves to a bottom bar or hamburger menu.

## Elevation & Depth
Depth is communicated through **Tonal Layering** and subtle borders rather than heavy shadows.

- **Level 0 (Background)**: `#0D1117` - The main application void.
- **Level 1 (Panels/Cards)**: `#161B22` - Used for sidebars and the primary content area. Border: 1px solid `#30363D`.
- **Level 2 (Modals/Popovers)**: `#21262D` - Floating elements that sit above the UI. These may use a very soft, high-spread shadow (Black, 25% opacity, 20px blur) to provide separation.
- **Active State**: Use a subtle inner-glow or a `2px` left-border in the primary orange hue to denote the "Active Trace" or "Selected Frame."

## Shapes
The shape language is disciplined and professional. 
- **Base Components**: Buttons and input fields use a `6px` radius.
- **Containers**: Cards and primary layout panels use the `8px` (`rounded-md`) to `12px` (`rounded-lg`) range. 
- **Status Pills**: Use a fully rounded (pill) shape to distinguish them from interactive buttons.

## Components

- **Buttons**: Primary buttons are solid Orange (`#F97316`) with white text. Secondary buttons use a "Ghost" style: subtle border, no fill, and white text that takes a background fill only on hover.
- **Logs/Terminal**: Content must be rendered in `code-sm` or `code-md`. Use a zebra-stripe background (`#161B22` and `#0D1117`) for long trace lists to maintain horizontal tracking.
- **Cards**: Use a `1px` border (`#30363D`) and a background of `#161B22`. Headlines within cards should use `label-caps` for metadata (e.g., TIMESTAMP, AGENT_ID).
- **Input Fields**: Dark backgrounds (`#0D1117`) with a 1px border. On focus, the border transitions to Primary Orange.
- **Trace Timeline**: A custom horizontal or vertical component. Use a thin line (`#30363D`) with nodes that change color based on the status (Success, Error, etc.). The "Current Playhead" is represented by a high-contrast white or orange line.
- **Chips/Badges**: Small, low-saturation backgrounds with high-saturation text (e.g., a dark red background with bright red text for "Error").