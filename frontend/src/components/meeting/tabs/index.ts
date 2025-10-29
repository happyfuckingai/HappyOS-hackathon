// Lazy load tab components for better code splitting
import { lazy } from 'react';

export const SettingsTab = lazy(() => import(/* webpackChunkName: "settings-tab" */ './SettingsTab'));
export const ChatTab = lazy(() => import(/* webpackChunkName: "chat-tab" */ './ChatTab'));
export const ShareRecordingTab = lazy(() => import(/* webpackChunkName: "share-tab" */ './ShareRecordingTab'));
export const AITab = lazy(() => import(/* webpackChunkName: "ai-tab" */ './AITab'));