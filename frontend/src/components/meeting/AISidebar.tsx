import React, { useState } from 'react';
import { Brain, ChevronLeft, ChevronRight, Maximize2, Minimize2 } from 'lucide-react';
import { Button } from '../ui/button';
import AIPanel from './AIPanel';

interface AISidebarProps {
  roomId: string;
  className?: string;
}

const AISidebar: React.FC<AISidebarProps> = ({ roomId, className = '' }) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  const toggleCollapsed = () => {
    setIsCollapsed(!isCollapsed);
    if (isExpanded) {
      setIsExpanded(false);
    }
  };

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
    if (isCollapsed) {
      setIsCollapsed(false);
    }
  };

  if (isCollapsed) {
    return (
      <div className={`w-12 h-full flex flex-col items-center justify-start pt-4 bg-slate-900/95 backdrop-blur-xl border-l border-white/10 ${className}`}>
        <Button
          onClick={toggleCollapsed}
          variant="ghost"
          size="sm"
          className="w-8 h-8 p-0 text-white/60 hover:text-white hover:bg-white/10"
        >
          <ChevronLeft className="w-4 h-4" />
        </Button>
        
        <div className="mt-4 writing-mode-vertical text-xs text-white/60 transform rotate-180">
          AI Assistant
        </div>
        
        <div className="mt-4">
          <Brain className="w-5 h-5 text-orange-400" />
        </div>
      </div>
    );
  }

  return (
    <div className={`${isExpanded ? 'w-96' : 'w-80'} h-full flex flex-col bg-slate-900/95 backdrop-blur-xl border-l border-white/10 transition-all duration-300 ${className}`}>
      {/* Header with Controls */}
      <div className="flex items-center justify-between p-3 border-b border-white/10">
        <div className="flex items-center space-x-2">
          <Brain className="w-4 h-4 text-orange-400" />
          <span className="text-sm font-medium text-white">AI Assistant</span>
        </div>
        
        <div className="flex items-center space-x-1">
          <Button
            onClick={toggleExpanded}
            variant="ghost"
            size="sm"
            className="w-6 h-6 p-0 text-white/60 hover:text-white hover:bg-white/10"
            title={isExpanded ? 'Minimize' : 'Maximize'}
          >
            {isExpanded ? (
              <Minimize2 className="w-3 h-3" />
            ) : (
              <Maximize2 className="w-3 h-3" />
            )}
          </Button>
          
          <Button
            onClick={toggleCollapsed}
            variant="ghost"
            size="sm"
            className="w-6 h-6 p-0 text-white/60 hover:text-white hover:bg-white/10"
            title="Collapse sidebar"
          >
            <ChevronRight className="w-3 h-3" />
          </Button>
        </div>
      </div>

      {/* AI Panel Content */}
      <div className="flex-1 overflow-hidden">
        <AIPanel roomId={roomId} className="h-full border-none bg-transparent" />
      </div>
    </div>
  );
};

export default AISidebar;