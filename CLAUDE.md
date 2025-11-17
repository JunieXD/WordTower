# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Language

Please use Chinese to communicate with me.
请使用简体中文与我交流。

## Project Overview

WordTower 是一个 Vue 3 + TypeScript 的渐进式 Web 应用（PWA），采用移动优先的响应式设计。应用包含身份验证、用户资料和游戏化体验，包括 RPG 风格的属性（HP、攻击力、暴击率等）。

## Development Commands

### Daily Development

```bash
npm install                 # Install dependencies
npm run dev                 # Start dev server with HTTPS on port 5173
npm run build               # Type-check and build for production
npm run preview             # Preview production build
npm run type-check          # Run TypeScript type checking
npm run lint                # Lint and auto-fix code
npm run format              # Format code with Prettier
npm run test:unit           # Run unit tests with Vitest
```

### Testing

```bash
npm run test:unit           # Run all unit tests
# For single test file, use: npx vitest src/path/to/test.spec.ts
```

## Architecture

### Technology Stack

- **Framework**: Vue 3 with Composition API (`<script setup>` syntax)
- **State Management**: Pinia stores
- **Routing**: Vue Router with lazy-loaded views
- **UI Components**:
  - Naive UI (auto-imported via unplugin-vue-components)
  - Reka UI (headless components)
  - Vant (mobile components)
- **Styling**: Tailwind CSS v4 via @tailwindcss/vite plugin
- **Icons**: Iconify Vue (registered globally as `<Icon>`)
- **HTTP Client**: Axios with custom request wrapper
- **PWA**: vite-plugin-pwa (currently commented out in vite.config.ts)

### Project Structure

```
src/
├── views/              # Route-level page components
├── layouts/            # Layout wrappers (DefaultLayout with sidebar/header/footer)
├── components/         # Reusable components
│   ├── AppHeader.vue  # Top navigation bar
│   ├── AppSidebar.vue # Desktop sidebar navigation
│   ├── FooterNav.vue  # Mobile bottom navigation
│   ├── NotificationContainer.vue  # Global notification renderer
│   └── NotificationItem.vue       # Single notification component
├── stores/            # Pinia state management
│   ├── userProfile.ts # User profile with cache-first strategy
│   ├── notification.ts # Global notification system
│   ├── library.ts     # Library-related state (new)
│   └── upgrade.ts     # Upgrade-related state (new)
├── router/            # Vue Router configuration
├── utils/             # Utility functions
│   └── request.ts    # Axios instance with interceptors
├── lib/              # Library utilities
└── assets/           # Static assets
```

### State Management (Pinia)

#### User Profile Store (`stores/userProfile.ts`)

- Implements cache-first strategy: shows cached data immediately, updates in background
- Profile interface includes game attributes: `max_hp`, `attack`, `crit_rate`, `max_floor`, `exp`, `coins`
- Methods: `getProfile(forceRefresh?)`, `updateProfile(partial)`, `clearProfile()`, `fetchProfile()`
- No localStorage persistence (data only in memory)

#### Notification Store (`stores/notification.ts`)

- Queue-based notification system with auto-generated IDs
- Supports variants: `default`, `destructive`
- Auto-dismiss with configurable duration (default 3 seconds)
- New notifications appear at the top (using `unshift`)
- Rendered by `NotificationContainer.vue` in App root

### Routing

Routes are defined in [router/index.ts](src/router/index.ts):

- All routes use lazy loading for code splitting
- Main routes wrapped in `DefaultLayout` with `requiresAuth: true` meta
- **Auth guard is ENABLED** (lines 40-57): checks userProfile, redirects to login if profile fetch fails
- Routes: `/home`, `/library`, `/upgrade`, `/leaderboard`, `/profile`, `/login`
- Uses `createWebHistory` for clean URLs

### HTTP Requests

The [utils/request.ts](src/utils/request.ts) utility wraps Axios with:

- **Base URL**: Empty string (relies on Vite proxy: `/api` → `http://localhost:8000`)
- **Timeout**: 5 seconds
- **withCredentials**: true (for cookie-based auth)
- **validateStatus**: accepts all status codes < 500 (4xx goes to success callback)
- **Request Interceptor**: Currently minimal (just logging)
- **Response Interceptor**: Minimal error handling (no auto-redirect on 401)

### Responsive Design

- **Desktop (lg+)**: Shows sidebar navigation, hides bottom nav
- **Mobile (<lg)**: Shows bottom nav, hides sidebar
- **Layout**: Flexbox-based with `DefaultLayout.vue`
- Mobile-first approach with Tailwind breakpoints

### PWA Configuration

**Currently disabled** (commented out in [vite.config.ts](vite.config.ts:22-79)):

- Would use auto-update service worker
- Would cache images (30 days) and API responses (5 minutes)
- Manifest configured for portrait mobile app experience

To enable PWA:

1. Uncomment lines 22-79 in vite.config.ts
2. Import VitePWA plugin at top of file
3. Add plugin to plugins array

### Auto-Import Setup

- Vue APIs (`ref`, `computed`, etc.) are auto-imported via unplugin-auto-import
- Naive UI components would be auto-registered IF unplugin-vue-components was configured (currently NOT set up)
- Components must be manually imported

### HTTPS Development

The dev server uses SSL certificates for HTTPS:

- Certificate files: `localhost+2-key.pem` and `localhost+2.pem` in project root
- Required for PWA testing and secure contexts
- Generate with mkcert if missing
- Server runs on `0.0.0.0:5173` with HTTPS

## Code Conventions

### Vue Components

- Use `<script setup lang="ts">` syntax exclusively
- Composition API with TypeScript
- Component names can be single-word (`vue/multi-word-component-names` is disabled)

### TypeScript

- Path alias `@/` maps to `src/`
- Strict typing enabled
- Use `vue-tsc` for type checking (not `tsc`)
- tsconfig is split: tsconfig.app.json, tsconfig.node.json, tsconfig.vitest.json

### API Integration

- Always use `request` instance from `@/utils/request`, not raw axios
- API endpoints should start with `/api/` to leverage Vite proxy
- Backend expected at `http://localhost:8000` in development
- Use `withCredentials: true` for cookie-based authentication

### Styling

- Tailwind CSS v4 via @tailwindcss/vite plugin (not PostCSS)
- Utility classes preferred
- Component-specific styles in `<style scoped>` when needed

## Important Notes

- **Node Version**: Requires Node.js ^20.19.0 or >=22.12.0
- **Auth Guard**: ENABLED in router - fetches profile before accessing protected routes
- **Icons**: Use `<Icon icon="icon-name" />` component (from @iconify/vue)
- **PWA**: Currently disabled, must be manually enabled in vite.config.ts
- **Backend URL**: Proxy configured to `http://localhost:8000` (not 8080!)
