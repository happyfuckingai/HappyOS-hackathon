import React, { useState, useEffect, useCallback, useMemo, memo } from 'react';
import { Brain, FileText, CheckSquare, MessageSquare, Settings, Volume2, VolumeX } from 'lucide-react';
import { useSSE } from '../../../contexts/SSEContext';
import { EventMessage } from '../../../types';
import { Button } from '../../ui/button';
import { ScrollArea } from '../../ui/scroll-area';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../../ui/tabs';

interface AITabProps {
  roomId: string;
}

const AITab: React.FC<AITabProps> = memo(({ roomId }) => {
  const [aiSettings, setAiSettings] = useState({
    autoNotes: true,
    actionDetection: true,
    voiceResponses: false,
    summaryFrequency: 'medium', // low, medium, high
  });
  
  const { events, isConnected, connectionError, connect } = useSSE();
  const [recentEvents, setRecentEvents] = useState<EventMessage[]>([]);

  // Memoize recent events to prevent unnecessary re-renders
  const recentEventsMemo = useMemo(() => {
    return events.slice(-10); // Last 10 events
  }, [events]);

  // Keep only recent events for display
  useEffect(() => {
    setRecentEvents(recentEventsMemo);
  }, [recentEventsMemo]);

  // Connect to SSE when component mounts
  useEffect(() => {
    if (roomId && !isConnected) {
      connect(roomId);
    }
  }, [roomId, isConnected, connect]);

  const handleSettingChange = useCallback((setting: keyof typeof aiSettings, value: any) => {
    setAiSettings(prev => ({
      ...prev,
      [setting]: value
    }));
    
    // TODO: Send settings update to backend
    console.log('AI setting changed:', setting, value);
  }, []);

  const getEventIcon = useCallback((type: EventMessage['type']) => {
    switch (type) {
      case 'note':
        return <FileText className="w-4 h-4 text-blue-400" />;
      case 'action':
        return <CheckSquare className="w-4 h-4 text-green-400" />;
      case 'agent_response':
        return <MessageSquare className="w-4 h-4 text-purple-400" />;
      default:
        return <Brain className="w-4 h-4 text-orange-400" />;
    }
  }, []);

  const getEventColor = useCallback((type: EventMessage['type']) => {
    switch (type) {
      case 'note':
        return 'bg-blue-500/20 border-blue-500/30';
      case 'action':
        return 'bg-green-500/20 border-green-500/30';
      case 'agent_response':
        return 'bg-purple-500/20 border-purple-500/30';
      default:
        return 'bg-orange-500/20 border-orange-500/30';
    }
  }, []);

  const formatTime = useCallback((timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }, []);

  const eventCounts = useMemo(() => {
    const notes = events.filter(e => e.type === 'note').length;
    const actions = events.filter(e => e.type === 'action').length;
    const responses = events.filter(e => e.type === 'agent_response').length;
    return { notes, actions, responses };
  }, [events]);



  return (
    <div className="h-full flex flex-col">
      {/* AI Status Header */}
      <div className="flex items-center justify-between pb-4 border-b border-white/10">
        <div className="flex items-center space-x-2">
          <Brain className="w-5 h-5 text-orange-400" />
          <h3 className="text-lg font-semibold text-white">AI Assistant</h3>
        </div>
        
        <div className="flex items-center space-x-2">
          {isConnected ? (
            <div className="flex items-center space-x-2 text-xs text-green-300">
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
              <span>Active</span>
            </div>
          ) : (
            <div className="flex items-center space-x-2 text-xs text-red-300">
              <div className="w-2 h-2 bg-red-400 rounded-full"></div>
              <span>Disconnected</span>
            </div>
          )}
        </div>
      </div>

      {/* Connection Error */}
      {connectionError && (
        <div className="p-3 mb-4 bg-red-500/20 border border-red-500/30 rounded-lg">
          <p className="text-sm text-red-300">{connectionError}</p>
        </div>
      )}

      {/* AI Statistics */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="p-3 rounded-lg bg-blue-500/20 border border-blue-500/30 text-center">
          <FileText className="w-4 h-4 mx-auto mb-1 text-blue-400" />
          <div className="text-lg font-semibold text-white">{eventCounts.notes}</div>
          <div className="text-xs text-blue-300">Notes</div>
        </div>
        
        <div className="p-3 rounded-lg bg-green-500/20 border border-green-500/30 text-center">
          <CheckSquare className="w-4 h-4 mx-auto mb-1 text-green-400" />
          <div className="text-lg font-semibold text-white">{eventCounts.actions}</div>
          <div className="text-xs text-green-300">Actions</div>
        </div>
        
        <div className="p-3 rounded-lg bg-purple-500/20 border border-purple-500/30 text-center">
          <MessageSquare className="w-4 h-4 mx-auto mb-1 text-purple-400" />
          <div className="text-lg font-semibold text-white">{eventCounts.responses}</div>
          <div className="text-xs text-purple-300">Responses</div>
        </div>
      </div>

      {/* Tabbed Content */}
      <div className="flex-1">
        <Tabs defaultValue="activity" className="h-full flex flex-col">
          <TabsList className="grid w-full grid-cols-2 mb-4 bg-white/5 backdrop-blur-md">
            <TabsTrigger value="activity" className="text-sm">
              Recent Activity
            </TabsTrigger>
            <TabsTrigger value="settings" className="text-sm">
              AI Settings
            </TabsTrigger>
          </TabsList>

          {/* Recent Activity Tab */}
          <TabsContent value="activity" className="flex-1">
            <ScrollArea className="h-full">
              <div className="space-y-3 pr-4">
                {recentEvents.length === 0 ? (
                  <div className="text-center py-8 text-white/60">
                    <Brain className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">No AI activity yet</p>
                    <p className="text-xs mt-1">AI will start analyzing the conversation automatically</p>
                  </div>
                ) : (
                  recentEvents.map((event, index) => (
                    <div
                      key={`${event.type}-${event.timestamp}-${index}`}
                      className={`p-3 rounded-lg border backdrop-blur-sm ${getEventColor(event.type)}`}
                    >
                      <div className="flex items-start space-x-3">
                        <div className="flex-shrink-0 mt-0.5">
                          {getEventIcon(event.type)}
                        </div>
                        
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium text-white/90 capitalize">
                              {event.type.replace('_', ' ')}
                            </span>
                            <span className="text-xs text-white/50">
                              {formatTime(event.timestamp)}
                            </span>
                          </div>
                          
                          <p className="text-sm text-white/80 leading-relaxed">
                            {event.type === 'note' && event.content}
                            {event.type === 'action' && event.description}
                            {event.type === 'agent_response' && event.message}
                          </p>
                          
                          {event.type === 'note' && 'speaker' in event && event.speaker && (
                            <div className="mt-1">
                              <span className="text-xs text-orange-400 bg-orange-500/20 px-2 py-1 rounded">
                                {event.speaker}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </ScrollArea>
          </TabsContent>

          {/* AI Settings Tab */}
          <TabsContent value="settings" className="flex-1">
            <ScrollArea className="h-full">
              <div className="space-y-4 pr-4">
                <div className="space-y-4">
                  <h4 className="text-sm font-medium text-white flex items-center space-x-2">
                    <Settings className="w-4 h-4" />
                    <span>AI Behavior</span>
                  </h4>
                  
                  {/* Auto Notes */}
                  <div className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10">
                    <div>
                      <div className="text-sm font-medium text-white">Automatic Notes</div>
                      <div className="text-xs text-white/60">AI captures key points automatically</div>
                    </div>
                    <button
                      onClick={() => handleSettingChange('autoNotes', !aiSettings.autoNotes)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        aiSettings.autoNotes ? 'bg-orange-500' : 'bg-white/20'
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          aiSettings.autoNotes ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>

                  {/* Action Detection */}
                  <div className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10">
                    <div>
                      <div className="text-sm font-medium text-white">Action Item Detection</div>
                      <div className="text-xs text-white/60">Identify tasks and action items</div>
                    </div>
                    <button
                      onClick={() => handleSettingChange('actionDetection', !aiSettings.actionDetection)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        aiSettings.actionDetection ? 'bg-orange-500' : 'bg-white/20'
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          aiSettings.actionDetection ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>

                  {/* Voice Responses */}
                  <div className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10">
                    <div>
                      <div className="text-sm font-medium text-white flex items-center space-x-2">
                        <span>Voice Responses</span>
                        {aiSettings.voiceResponses ? (
                          <Volume2 className="w-3 h-3 text-green-400" />
                        ) : (
                          <VolumeX className="w-3 h-3 text-white/40" />
                        )}
                      </div>
                      <div className="text-xs text-white/60">AI speaks responses aloud</div>
                    </div>
                    <button
                      onClick={() => handleSettingChange('voiceResponses', !aiSettings.voiceResponses)}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        aiSettings.voiceResponses ? 'bg-orange-500' : 'bg-white/20'
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                          aiSettings.voiceResponses ? 'translate-x-6' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>

                  {/* Summary Frequency */}
                  <div className="p-3 rounded-lg bg-white/5 border border-white/10">
                    <div className="text-sm font-medium text-white mb-2">Summary Frequency</div>
                    <div className="text-xs text-white/60 mb-3">How often AI provides meeting summaries</div>
                    
                    <div className="grid grid-cols-3 gap-2">
                      {['low', 'medium', 'high'].map((freq) => (
                        <Button
                          key={freq}
                          onClick={() => handleSettingChange('summaryFrequency', freq)}
                          variant={aiSettings.summaryFrequency === freq ? 'default' : 'outline'}
                          size="sm"
                          className={`text-xs ${
                            aiSettings.summaryFrequency === freq
                              ? 'bg-orange-500 hover:bg-orange-600'
                              : 'border-white/20 hover:bg-white/10'
                          }`}
                        >
                          {freq.charAt(0).toUpperCase() + freq.slice(1)}
                        </Button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* AI Status Info */}
                <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                  <div className="text-sm font-medium text-blue-300 mb-1">AI Status</div>
                  <div className="text-xs text-blue-200 space-y-1">
                    <div>• Real-time conversation analysis</div>
                    <div>• Automatic note-taking and action detection</div>
                    <div>• Context-aware responses</div>
                    <div>• Meeting summary generation</div>
                  </div>
                </div>
              </div>
            </ScrollArea>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
});

AITab.displayName = 'AITab';

export default AITab;