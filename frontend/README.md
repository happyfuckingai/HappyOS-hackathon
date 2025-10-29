# MeetMind Frontend (New)

This is the new, clean implementation of the MeetMind frontend based on our design specifications.

## Architecture

This frontend follows a clean, minimal architecture with:

- **React 18** with TypeScript
- **Tailwind CSS** with custom glassmorphism design system
- **React Router v6** for routing
- **Context API** for state management
- **LiveKit** for video/audio (to be implemented)
- **Server-Sent Events (SSE)** for real-time AI features

## Design Principles

1. **Minimal Interface**: Clean, distraction-free meeting experience
2. **Glassmorphism**: Consistent use of `bg-white/5 backdrop-blur-md border border-white/10`
3. **Everything Behind Plus**: All controls accessible through FAB menu
4. **Mobile-First**: Responsive design that works on all devices
5. **Brand Consistency**: Orange accents on blue base theme

## Project Structure

```
src/
├── components/
│   ├── layout/
│   │   ├── AppShell.tsx
│   │   └── Header.tsx
│   ├── auth/
│   │   └── AuthGuard.tsx
│   └── common/
│       └── ErrorBoundary.tsx
├── contexts/
│   ├── AuthContext.tsx
│   ├── MeetingContext.tsx
│   └── SSEContext.tsx
├── pages/
│   ├── Landing.tsx
│   ├── Auth.tsx
│   ├── Lobby.tsx
│   └── Meeting.tsx
├── lib/
│   ├── api.ts
│   └── utils.ts
├── types/
│   └── index.ts
├── App.tsx
└── index.tsx
```

## Getting Started

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm start
```

3. Open [http://localhost:3000](http://localhost:3000) to view it in the browser.

## Current Implementation Status

### ✅ Completed (Task 1)
- [x] Tailwind CSS configuration with custom theme
- [x] CSS custom properties for brand colors and glassmorphism
- [x] TypeScript interfaces for core data models
- [x] Basic project structure and routing
- [x] Authentication flow (UI only)
- [x] Landing, Auth, Lobby, and basic Meeting pages
- [x] Context providers for Auth, Meeting, and SSE
- [x] API layer structure
- [x] Error boundary and route guards

### 🚧 Next Tasks
- [ ] shadcn/ui component installation and configuration
- [ ] LiveKit integration for video/audio
- [ ] FAB menu system
- [ ] Real-time AI features
- [ ] Performance optimizations
- [ ] Comprehensive testing

## Design System

### Colors
- **Brand Blue**: `#0A2540`
- **Brand Orange**: `#FF6A3D`
- **Glass Background**: `rgba(255, 255, 255, 0.05)`
- **Glass Border**: `rgba(255, 255, 255, 0.1)`

### Typography
- **Font Family**: Plus Jakarta Sans
- **Display**: 2rem, semibold
- **Title**: 1.5rem, semibold
- **Heading**: 1.25rem, medium
- **Body**: 1rem, normal

### Glassmorphism Utilities
- `.glass-panel`: Standard glassmorphism panel
- `.glass-button`: Interactive glassmorphism button
- `.glass-card`: Card with glassmorphism styling
- `.glass-input`: Form input with glassmorphism styling

## Environment Variables

Create a `.env` file in the root directory:

```
REACT_APP_API_URL=http://localhost:8000
```

## Available Scripts

- `npm start`: Runs the app in development mode
- `npm build`: Builds the app for production
- `npm test`: Launches the test runner
- `npm eject`: Ejects from Create React App (not recommended)

## Contributing

This is a clean implementation following our design specifications. Please maintain the established patterns and design principles when adding new features.