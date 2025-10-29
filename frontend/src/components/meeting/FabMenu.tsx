import React, { useState, useCallback, memo, Suspense } from 'react';
import { Plus } from 'lucide-react';
import { FabMenuProps } from '../../types';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '../ui/sheet';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '../ui/tabs';
import { SettingsTab, ChatTab, ShareRecordingTab, AITab } from './tabs';

// Tab loading fallback
const TabLoader: React.FC = () => (
  <div className="flex items-center justify-center h-32">
    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-orange-500"></div>
  </div>
);

const FabMenu: React.FC<FabMenuProps> = memo(({ roomId }) => {
  const [isOpen, setIsOpen] = useState(false);

  const handleOpenChange = useCallback((open: boolean) => {
    setIsOpen(open);
  }, []);

  return (
    <Sheet open={isOpen} onOpenChange={handleOpenChange}>
      {/* FAB Button */}
      <SheetTrigger asChild>
        <button 
          className={`fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full flex items-center justify-center transition-all duration-300 shadow-lg hover:scale-105 active:scale-95 ${
            isOpen 
              ? 'bg-red-500 hover:bg-red-600 rotate-45' 
              : 'bg-orange-500 hover:bg-orange-600'
          }`}
          style={{ 
            boxShadow: isOpen 
              ? '0 0 20px rgba(239, 68, 68, 0.4), 0 4px 20px rgba(0, 0, 0, 0.3)' 
              : '0 0 20px rgba(255, 106, 61, 0.4), 0 4px 20px rgba(0, 0, 0, 0.3)' 
          }}
          aria-label={isOpen ? 'Close meeting controls' : 'Open meeting controls'}
        >
          <Plus className="w-6 h-6 text-white transition-transform duration-300" />
        </button>
      </SheetTrigger>

      {/* Sheet Content */}
      <SheetContent 
        side="bottom" 
        className="h-[80vh] max-h-[600px] rounded-t-2xl border-t border-white/20 bg-slate-900/95 backdrop-blur-xl"
      >
        <SheetHeader className="pb-4">
          <SheetTitle className="text-xl font-semibold text-white text-center">
            Meeting Controls
          </SheetTitle>
        </SheetHeader>

        {/* Tabbed Interface */}
        <Tabs defaultValue="ai" className="flex-1 flex flex-col">
          <TabsList className="grid w-full grid-cols-4 mb-4 bg-white/5 backdrop-blur-md">
            <TabsTrigger value="ai" className="text-sm">
              AI
            </TabsTrigger>
            <TabsTrigger value="settings" className="text-sm">
              Settings
            </TabsTrigger>
            <TabsTrigger value="chat" className="text-sm">
              Chat
            </TabsTrigger>
            <TabsTrigger value="share" className="text-sm">
              Share
            </TabsTrigger>
          </TabsList>

          <div className="flex-1 overflow-hidden">
            <TabsContent value="ai" className="h-full">
              <Suspense fallback={<TabLoader />}>
                <AITab roomId={roomId} />
              </Suspense>
            </TabsContent>
            
            <TabsContent value="settings" className="h-full">
              <Suspense fallback={<TabLoader />}>
                <SettingsTab roomId={roomId} />
              </Suspense>
            </TabsContent>
            
            <TabsContent value="chat" className="h-full">
              <Suspense fallback={<TabLoader />}>
                <ChatTab roomId={roomId} />
              </Suspense>
            </TabsContent>
            
            <TabsContent value="share" className="h-full">
              <Suspense fallback={<TabLoader />}>
                <ShareRecordingTab roomId={roomId} />
              </Suspense>
            </TabsContent>
          </div>
        </Tabs>
      </SheetContent>
    </Sheet>
  );
});

FabMenu.displayName = 'FabMenu';

export default FabMenu;