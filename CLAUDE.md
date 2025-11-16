# CLAUDE.md

## 请使用中文和我对话

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WordTower is a Vue 3 + TypeScript Progressive Web Application (PWA) with a mobile-first responsive design. The app features authentication, user profiles, and a gamified experience with RPG-like attributes (HP, attack, crit rate, etc.).

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
  - Naive UI (auto-imported)
  - Reka UI (headless components)
  - Vant (mobile components)
  - Custom components in `src/components/ui/`
- **Styling**: Tailwind CSS v4 with custom utilities
- **Icons**: Iconify Vue (registered globally as `<Icon>`)
- **HTTP Client**: Axios with custom request wrapper
- **PWA**: vite-plugin-pwa with workbox for offline support

### Project Structure

```

src/
├── views/              # Route-level page components
├── layouts/            # Layout wrappers (DefaultLayout with sidebar/header/footer)
├── components/         # Reusable components
│   ├── ui/            # UI component library (shadcn-style)
│   ├── AppHeader.vue  # Top navigation bar
│   ├── AppSidebar.vue # Desktop sidebar navigation
│   └── FooterNav.vue  # Mobile bottom navigation
├── stores/            # Pinia state management
│   ├── auth.ts       # Token management with localStorage persistence
│   ├── userProfile.ts # User profile with cache-first strategy
│   └── notification.ts # Global notification system
├── router/            # Vue Router configuration
├── utils/             # Utility functions
│   └── request.ts    # Axios instance with interceptors
├── lib/              # Library utilities
└── assets/           # Static assets
```

### State Management (Pinia)

#### Auth Store (`stores/auth.ts`)
- Manages JWT token in localStorage
- Provides `isAuthenticated` computed property
- Methods: `setToken()`, `clearToken()`, `initToken()`

#### User Profile Store (`stores/userProfile.ts`)
- Implements cache-first strategy: shows cached data immediately, updates in background
- Profile includes game attributes: `maxHp`, `attack`, `critRate`, `maxFloor`, `exp`, `coins`
- Methods: `getProfile(forceRefresh?)`, `updateProfile(partial)`, `clearProfile()`
- Automatically persists to localStorage

#### Notification Store (`stores/notification.ts`)
- Queue-based notification system
- Supports variants: `default`, `destructive`
- Auto-dismiss with configurable duration
- Rendered by `NotificationContainer.vue` in App root

### Routing

Routes are defined in `src/router/index.ts`:
- All routes use lazy loading for code splitting
- Main routes wrapped in `DefaultLayout` with `requiresAuth: true` meta
- Auth guard is currently commented out (lines 39-47)
- Routes: `/home`, `/library`, `/upgrade`, `/leaderboard`, `/profile`, `/login`

### HTTP Requests

The `request.ts` utility wraps Axios with:
- **Base URL**: Empty string (relies on Vite proxy: `/api` → `http://localhost:8080`)
- **Request Interceptor**: Automatically adds `Authorization: Bearer {token}` header
- **Response Interceptor**: Handles 401 errors by clearing token and redirecting to login
- **Timeout**: 5 seconds

### Responsive Design

- **Desktop (lg+)**: Shows sidebar navigation, hides bottom nav
- **Mobile (<lg)**: Shows bottom nav, hides sidebar
- **Layout**: Flexbox-based with `DefaultLayout.vue`
- Mobile-first approach with Tailwind breakpoints

### PWA Configuration

Configured in `vite.config.ts`:
- Auto-update service worker
- Caches images (30 days) and API responses (5 minutes)
- Offline-capable with runtime caching strategies
- Manifest configured for portrait mobile app experience

### Auto-Import Setup

- Vue APIs (`ref`, `computed`, etc.) are auto-imported
- Naive UI composables (`useDialog`, `useMessage`, etc.) are auto-imported
- Naive UI components are auto-registered (no manual imports needed)
- Components in `src/components/ui/` use manual imports

### HTTPS Development

The dev server requires SSL certificates:
- Certificate files: `localhost+2-key.pem` and `localhost+2.pem` in project root
- These are needed for PWA testing and secure contexts
- Generate with mkcert if missing

## Code Conventions

### Vue Components
- Use `<script setup lang="ts">` syntax exclusively
- Composition API with TypeScript
- Component names can be single-word (vue/multi-word-component-names is disabled)

### TypeScript
- Path alias `@/` maps to `src/`
- Strict typing enabled
- Use `vue-tsc` for type checking (not `tsc`)

### API Integration
- Always use `request` instance from `@/utils/request`, not raw axios
- API endpoints should start with `/api/` to leverage Vite proxy
- Backend expected at `http://localhost:8080` in development

### Styling
- Tailwind utility classes preferred
- Component-specific styles in `<style scoped>` when needed
- Custom utilities via `tailwind-merge` and `clsx` in `lib/utils.ts`

## Important Notes

- **Node Version**: Requires Node.js ^20.19.0 or >=22.12.0
- **Auth Guard**: Currently disabled in router (see router/index.ts:39-47)
- **Icons**: Use `<Icon icon="icon-name" />` component (from @iconify/vue)
- **Global State**: Avoid prop drilling; use Pinia stores for shared state
- **PWA Updates**: Service worker auto-updates, users see new version on next load
