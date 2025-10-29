import React, { useState, useEffect, useRef } from 'react';
import { Brain, FileText, CheckSquare, MessageSquare, Loader2, AlertCircle, RefreshCw } from 'lucide-react';
import { useSSE } from '../../contexts/SSEContext';
import { EventMessage } from '../../types';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../ui/tabs';
import { ScrollArea } from '../ui/scroll-area';
import { Button } from '../ui/button';

interface AIPanelProps {
  roomId: string;
  className?: string;
}

interface NoteItem {
  id: string;
  content: string;
  speaker?: string;
  timestamp: string;
  confidence?: number;
}

interface ActionItem {
  id: string;
  description: string;
  assignee?: string;
  dueDate?: string;
  status: 'pending' | 'completed';
  priority?: 'low' | 'medium' | 'high';
  timestamp: string;
}

interface AgentResponseItem {
  id: string;
  message: string;
  context?: any;
  timestamp: string;
  persona?: string;
}

const AIPanel: React.FC<AIPanelProps> = ({ roomId, className = '' }) => {
  const [notes, setNotes] = useState<NoteItem[]>([]);
  const [actions, setActions] = useState<ActionItem[]>([]);
  const [agentResponses, setAgentResponses] = useState<AgentResponseItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const { events, isConnected, connectionError, connect, disconnect } = useSSE();
  const notesEndRef = useRef<HTMLDivElement>(null);
  const actionsEndRef = useRef<HTMLDivElement>(null);
  const responsesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new items arrive
  useEffect(() => {
    notesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [notes]);

  useEffect(() => {
    actionsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [actions]);

  useEffect(() => {
    responsesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [agentResponses]);

  // Process SSE events into structured data
  useEffect(() => {
    events.forEach((event: EventMessage) => {
      switch (event.type) {
        case 'note':
          const noteItem: NoteItem = {
            id: `note-${Date.now()}-${Math.random()}`,
            content: event.content,
            speaker: event.speaker,
            timestamp: event.timestamp,
          };
          setNotes(prev => {
            // Avoid duplicates
            if (prev.some(n => n.content === noteItem.content && n.timestamp === noteItem.timestamp)) {
              return prev;
            }
            return [...prev, noteItem];
          });
          break;

        case 'action':
          const actionItem: ActionItem = {
            id: `action-${Date.now()}-${Math.random()}`,
            description: event.description,
            assignee: event.assignee,
            dueDate: event.dueDate,
            status: 'pending',
            timestamp: event.timestamp,
          };
          setActions(prev => {
            // Avoid duplicates
            if (prev.some(a => a.description === actionItem.description && a.timestamp === actionItem.timestamp)) {
              return prev;
            }
            return [...prev, actionItem];
          });
          break;

        case 'agent_response':
          const responseItem: AgentResponseItem = {
            id: `response-${Date.now()}-${Math.random()}`,
            message: event.message,
            context: event.context,
            timestamp: event.timestamp,
            persona: event.context?.persona,
          };
          setAgentResponses(prev => {
            // Avoid duplicates
            if (prev.some(r => r.message === responseItem.message && r.timestamp === responseItem.timestamp)) {
              return prev;
            }
            return [...prev, responseItem];
          });
          break;
      }
    });
  }, [events]);

  // Connect to SSE when component mounts
  useEffect(() => {
    if (roomId && !isConnected) {
      connect(roomId);
    }
    
    return () => {
      // Don't disconnect here as other components might be using SSE
    };
  }, [roomId, isConnected, connect]);

  const handleRetryConnection = () => {
    setError(null);
    if (roomId) {
      connect(roomId);
    }
  };

  const toggleActionStatus = (actionId: string) => {
    setActions(prev => prev.map(action => 
      action.id === actionId 
        ? { ...action, status: action.status === 'pending' ? 'completed' : 'pending' }
        : action
    ));
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const formatDate = (timestamp: string) => {
    return new Date(timestamp).toLocaleDateString();
  };

  const getPriorityColor = (priority?: string) => {
    switch (priority) {
      case 'high': return 'text-red-400 bg-red-500/20';
      case 'medium': return 'text-yellow-400 bg-yellow-500/20';
      case 'low': return 'text-green-400 bg-green-500/20';
      default: return 'text-blue-400 bg-blue-500/20';
    }
  };

  const ConnectionStatus = () => {
    if (connectionError) {
      return (
        <div className="flex items-center justify-between p-3 mb-4 bg-red-500/20 border border-red-500/30 rounded-lg">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-red-400" />
            <span className="text-sm text-red-300">Connection Error</span>
          </div>
          <Button
            onClick={handleRetryConnection}
            size="sm"
            variant="outline"
            className="h-8 px-3 text-xs border-red-500/30 hover:bg-red-500/20"
          >
            <RefreshCw className="w-3 h-3 mr-1" />
            Retry
          </Button>
        </div>
      );
    }

    if (!isConnected) {
      return (
        <div className="flex items-center space-x-2 p-3 mb-4 bg-yellow-500/20 border border-yellow-500/30 rounded-lg">
          <Loader2 className="w-4 h-4 text-yellow-400 animate-spin" />
          <span className="text-sm text-yellow-300">Connecting to AI services...</span>
        </div>
      );
    }

    return (
      <div className="flex items-center space-x-2 p-3 mb-4 bg-green-500/20 border border-green-500/30 rounded-lg">
        <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
        <span className="text-sm text-green-300">AI Assistant Connected</span>
      </div>
    );
  };

  return (
    <div className={`h-full flex flex-col bg-slate-900/95 backdrop-blur-xl rounded-lg border border-white/10 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-white/10">
        <div className="flex items-center space-x-2">
          <Brain className="w-5 h-5 text-orange-400" />
          <h3 className="text-lg font-semibold text-white">AI Assistant</h3>
        </div>
        
        <div className="flex items-center space-x-2 text-xs text-white/60">
          <span>{events.length} events</span>
        </div>
      </div>

      {/* Connection Status */}
      <div className="px-4 pt-4">
        <ConnectionStatus />
      </div>

      {/* Tabbed Content */}
      <div className="flex-1 px-4 pb-4">
        <Tabs defaultValue="notes" className="h-full flex flex-col">
          <TabsList className="grid w-full grid-cols-3 mb-4 bg-white/5 backdrop-blur-md">
            <TabsTrigger value="notes" className="text-sm flex items-center space-x-1">
              <FileText className="w-3 h-3" />
              <span>Notes</span>
              {notes.length > 0 && (
                <span className="ml-1 px-1.5 py-0.5 text-xs bg-orange-500 text-white rounded-full">
                  {notes.length}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="actions" className="text-sm flex items-center space-x-1">
              <CheckSquare className="w-3 h-3" />
              <span>Actions</span>
              {actions.length > 0 && (
                <span className="ml-1 px-1.5 py-0.5 text-xs bg-orange-500 text-white rounded-full">
                  {actions.length}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger value="responses" className="text-sm flex items-center space-x-1">
              <MessageSquare className="w-3 h-3" />
              <span>Responses</span>
              {agentResponses.length > 0 && (
                <span className="ml-1 px-1.5 py-0.5 text-xs bg-orange-500 text-white rounded-full">
                  {agentResponses.length}
                </span>
              )}
            </TabsTrigger>
          </TabsList>

          {/* Notes Tab */}
          <TabsContent value="notes" className="flex-1">
            <ScrollArea className="h-full">
              <div className="space-y-3 pr-4">
                {notes.length === 0 ? (
                  <div className="text-center py-8 text-white/60">
                    <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">No notes yet</p>
                    <p className="text-xs mt-1">AI will automatically capture key points from the conversation</p>
                  </div>
                ) : (
                  notes.map((note) => (
                    <div
                      key={note.id}
                      className="p-3 rounded-lg bg-white/5 border border-white/10 backdrop-blur-sm"
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center space-x-2">
                          {note.speaker && (
                            <span className="text-xs font-medium text-orange-400 bg-orange-500/20 px-2 py-1 rounded">
                              {note.speaker}
                            </span>
                          )}
                        </div>
                        <span className="text-xs text-white/50">
                          {formatTime(note.timestamp)}
                        </span>
                      </div>
                      <p className="text-sm text-white/80 leading-relaxed">
                        {note.content}
                      </p>
                    </div>
                  ))
                )}
                <div ref={notesEndRef} />
              </div>
            </ScrollArea>
          </TabsContent>

          {/* Actions Tab */}
          <TabsContent value="actions" className="flex-1">
            <ScrollArea className="h-full">
              <div className="space-y-3 pr-4">
                {actions.length === 0 ? (
                  <div className="text-center py-8 text-white/60">
                    <CheckSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">No action items yet</p>
                    <p className="text-xs mt-1">AI will identify tasks and action items from the discussion</p>
                  </div>
                ) : (
                  actions.map((action) => (
                    <div
                      key={action.id}
                      className={`p-3 rounded-lg border backdrop-blur-sm transition-all ${
                        action.status === 'completed' 
                          ? 'bg-green-500/10 border-green-500/30' 
                          : 'bg-white/5 border-white/10'
                      }`}
                    >
                      <div className="flex items-start space-x-3">
                        <button
                          onClick={() => toggleActionStatus(action.id)}
                          className={`mt-0.5 w-4 h-4 rounded border-2 flex items-center justify-center transition-colors ${
                            action.status === 'completed'
                              ? 'bg-green-500 border-green-500'
                              : 'border-white/30 hover:border-orange-400'
                          }`}
                        >
                          {action.status === 'completed' && (
                            <CheckSquare className="w-3 h-3 text-white" />
                          )}
                        </button>
                        
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center space-x-2">
                              {action.priority && (
                                <span className={`text-xs px-2 py-1 rounded ${getPriorityColor(action.priority)}`}>
                                  {action.priority}
                                </span>
                              )}
                            </div>
                            <span className="text-xs text-white/50">
                              {formatTime(action.timestamp)}
                            </span>
                          </div>
                          
                          <p className={`text-sm leading-relaxed ${
                            action.status === 'completed' 
                              ? 'text-white/60 line-through' 
                              : 'text-white/80'
                          }`}>
                            {action.description}
                          </p>
                          
                          {(action.assignee || action.dueDate) && (
                            <div className="flex items-center space-x-4 mt-2 text-xs text-white/60">
                              {action.assignee && (
                                <span>Assigned to: {action.assignee}</span>
                              )}
                              {action.dueDate && (
                                <span>Due: {formatDate(action.dueDate)}</span>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                )}
                <div ref={actionsEndRef} />
              </div>
            </ScrollArea>
          </TabsContent>

          {/* Agent Responses Tab */}
          <TabsContent value="responses" className="flex-1">
            <ScrollArea className="h-full">
              <div className="space-y-3 pr-4">
                {agentResponses.length === 0 ? (
                  <div className="text-center py-8 text-white/60">
                    <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">No agent responses yet</p>
                    <p className="text-xs mt-1">AI agent will respond when addressed or when providing insights</p>
                  </div>
                ) : (
                  agentResponses.map((response) => (
                    <div
                      key={response.id}
                      className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/30 backdrop-blur-sm"
                    >
                      <div className="flex items-start space-x-3">
                        <div className="flex-shrink-0 mt-0.5">
                          <Brain className="w-4 h-4 text-blue-400" />
                        </div>
                        
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center space-x-2">
                              <span className="text-sm font-medium text-blue-300">
                                AI Assistant
                              </span>
                              {response.persona && (
                                <span className="text-xs text-blue-400 bg-blue-500/20 px-2 py-1 rounded">
                                  {response.persona}
                                </span>
                              )}
                            </div>
                            <span className="text-xs text-white/50">
                              {formatTime(response.timestamp)}
                            </span>
                          </div>
                          
                          <p className="text-sm text-white/80 leading-relaxed whitespace-pre-wrap">
                            {response.message}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))
                )}
                <div ref={responsesEndRef} />
              </div>
            </ScrollArea>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
};

export default AIPanel;