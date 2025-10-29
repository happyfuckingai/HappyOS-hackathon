// Core Data Models

export interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  role: 'user' | 'admin';
}

export interface Meeting {
  id: string;
  roomId: string;
  title?: string;
  createdBy: string;
  createdAt: string;
  status: 'active' | 'ended';
  participants: Participant[];
}

export interface Participant {
  id: string;
  name: string;
  avatar?: string;
  isMuted: boolean;
  isCameraOff: boolean;
  isHandRaised: boolean;
  joinedAt: string;
}

// AI Event Models
export interface NoteEvent {
  type: 'note';
  content: string;
  speaker?: string;
  timestamp: string;
}

export interface ActionEvent {
  type: 'action';
  description: string;
  assignee?: string;
  dueDate?: string;
  timestamp: string;
}

export interface AgentResponse {
  type: 'agent_response';
  message: string;
  context?: any;
  timestamp: string;
}

export type EventMessage = NoteEvent | ActionEvent | AgentResponse;

// Component Props Types
export interface AppShellProps {
  children: React.ReactNode;
}

export interface HeaderProps {
  showMeetingControls?: boolean;
  meetingId?: string;
}

export interface AuthPageProps {
  mode: 'login' | 'register';
}

export interface MeetingPageProps {
  roomId: string;
}

export interface VideoGridProps {
  roomId: string;
}

export interface SideParticipantsProps {
  roomId: string;
}

export interface FabMenuProps {
  roomId: string;
}

// Context Types
export interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  logout: () => Promise<void>;
}

export interface MeetingContextType {
  roomId: string | null;
  participants: Participant[];
  isConnected: boolean;
  joinMeeting: (roomId: string) => Promise<void>;
  leaveMeeting: () => Promise<void>;
  createMeeting: (title?: string) => Promise<string>;
}

export interface SSEContextType {
  events: EventMessage[];
  isConnected: boolean;
  sendMessage: (message: any) => Promise<void>;
  connect: (roomId: string) => void;
  disconnect: () => void;
  // Extended interface for better UX
  connectionError?: string | null;
  isReconnecting?: boolean;
  clearEvents?: () => void;
  getEventsByType?: (type: EventMessage['type']) => EventMessage[];
  isOnline?: boolean;
}

// Error Handling Types
export interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

export interface ApiError {
  message: string;
  status: number;
  code?: string;
}

export interface ApiResponse<T = any> {
  data?: T;
  error?: ApiError;
  success: boolean;
}

// Form Types
export interface LoginFormData {
  email: string;
  password: string;
}

export interface RegisterFormData {
  email: string;
  password: string;
  name: string;
  confirmPassword: string;
}

export interface CreateMeetingFormData {
  title?: string;
}

export interface JoinMeetingFormData {
  roomId: string;
}

// LiveKit Types
export interface LiveKitConnectionState {
  isConnected: boolean;
  isConnecting: boolean;
  error?: string;
}

export interface MediaDeviceInfo {
  deviceId: string;
  label: string;
  kind: 'audioinput' | 'videoinput' | 'audiooutput';
}

// Utility Types
export type LoadingState = 'idle' | 'loading' | 'success' | 'error';

export interface LoadingManager {
  isLoading: boolean;
  error?: string;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

// Route Types
export type RouteGuardType = 'auth' | 'admin';

export interface RouteGuardProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

// Theme Types
export interface ThemeContextType {
  isDark: boolean;
  toggleTheme: () => void;
}

// Performance Types
export interface PerformanceMetrics {
  renderTime: number;
  componentCount: number;
  memoryUsage?: number;
}

// WebSocket Types
export interface WebSocketMessage {
  type: string;
  payload: any;
  timestamp: string;
}

export interface WebSocketContextType {
  isConnected: boolean;
  sendMessage: (message: WebSocketMessage) => void;
  lastMessage: WebSocketMessage | null;
  // Extended interface for better UX
  connectionError?: string | null;
  isReconnecting?: boolean;
  connect?: (roomId: string) => void;
  disconnect?: () => void;
  sendChatMessage?: (content: string, roomId: string) => void;
  sendTypingIndicator?: (isTyping: boolean, roomId: string) => void;
  retry?: () => void;
}

// Re-export UI Resource types
export * from './ui-resources';