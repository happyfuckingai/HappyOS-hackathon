import React, { useState, useEffect } from 'react';
import { Mic, MicOff, Video, VideoOff, Volume2, Users, LogOut } from 'lucide-react';
import { useMeeting } from '../../../contexts/MeetingContext';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../ui/button';
import { ScrollArea } from '../../ui/scroll-area';

interface SettingsTabProps {
  roomId: string;
}

interface MediaDevice {
  deviceId: string;
  label: string;
  kind: 'audioinput' | 'videoinput' | 'audiooutput';
}

const SettingsTab: React.FC<SettingsTabProps> = ({ roomId }) => {
  const { leaveMeeting } = useMeeting();
  const navigate = useNavigate();
  
  // Media controls state
  const [isMuted, setIsMuted] = useState(false);
  const [isCameraOff, setIsCameraOff] = useState(false);
  const [volume, setVolume] = useState(75);
  const [videoQuality, setVideoQuality] = useState('720p');
  
  // Device selection state
  const [audioDevices, setAudioDevices] = useState<MediaDevice[]>([]);
  const [videoDevices, setVideoDevices] = useState<MediaDevice[]>([]);
  const [audioOutputDevices, setAudioOutputDevices] = useState<MediaDevice[]>([]);
  const [selectedAudioInput, setSelectedAudioInput] = useState('');
  const [selectedVideoInput, setSelectedVideoInput] = useState('');
  const [selectedAudioOutput, setSelectedAudioOutput] = useState('');
  
  // Accessibility settings
  const [highContrast, setHighContrast] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [showCaptions, setShowCaptions] = useState(false);

  // Load available media devices
  useEffect(() => {
    const loadDevices = async () => {
      try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        
        const audioInputs = devices.filter(device => device.kind === 'audioinput');
        const videoInputs = devices.filter(device => device.kind === 'videoinput');
        const audioOutputs = devices.filter(device => device.kind === 'audiooutput');
        
        setAudioDevices(audioInputs.map(device => ({
          deviceId: device.deviceId,
          label: device.label || `Microphone ${audioInputs.indexOf(device) + 1}`,
          kind: 'audioinput'
        })));
        
        setVideoDevices(videoInputs.map(device => ({
          deviceId: device.deviceId,
          label: device.label || `Camera ${videoInputs.indexOf(device) + 1}`,
          kind: 'videoinput'
        })));
        
        setAudioOutputDevices(audioOutputs.map(device => ({
          deviceId: device.deviceId,
          label: device.label || `Speaker ${audioOutputs.indexOf(device) + 1}`,
          kind: 'audiooutput'
        })));
        
        // Set default selections
        if (audioInputs.length > 0) setSelectedAudioInput(audioInputs[0].deviceId);
        if (videoInputs.length > 0) setSelectedVideoInput(videoInputs[0].deviceId);
        if (audioOutputs.length > 0) setSelectedAudioOutput(audioOutputs[0].deviceId);
        
      } catch (error) {
        console.error('Failed to load media devices:', error);
      }
    };

    loadDevices();
  }, []);

  const handleToggleMic = () => {
    setIsMuted(!isMuted);
    // TODO: Integrate with LiveKit to actually mute/unmute
  };

  const handleToggleCamera = () => {
    setIsCameraOff(!isCameraOff);
    // TODO: Integrate with LiveKit to actually turn camera on/off
  };

  const handleVolumeChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newVolume = parseInt(event.target.value);
    setVolume(newVolume);
    // TODO: Apply volume change to audio output
  };

  const handleLeaveMeeting = async () => {
    if (window.confirm('Are you sure you want to leave the meeting?')) {
      try {
        await leaveMeeting();
        navigate('/lobby');
      } catch (error) {
        console.error('Failed to leave meeting:', error);
        navigate('/lobby');
      }
    }
  };

  return (
    <ScrollArea className="h-full pr-4">
      <div className="space-y-6">
        {/* Quick Controls */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-white mb-3">Quick Controls</h3>
          
          <div className="grid grid-cols-2 gap-3">
            <Button
              onClick={handleToggleMic}
              variant="outline"
              className={`h-16 flex flex-col items-center justify-center space-y-2 ${
                isMuted 
                  ? 'bg-red-500/20 border-red-500/60 text-red-400 hover:bg-red-500/30' 
                  : 'glass-button text-white hover:bg-white/15'
              }`}
            >
              {isMuted ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
              <span className="text-xs">{isMuted ? 'Unmute' : 'Mute'}</span>
            </Button>
            
            <Button
              onClick={handleToggleCamera}
              variant="outline"
              className={`h-16 flex flex-col items-center justify-center space-y-2 ${
                isCameraOff 
                  ? 'bg-red-500/20 border-red-500/60 text-red-400 hover:bg-red-500/30' 
                  : 'glass-button text-white hover:bg-white/15'
              }`}
            >
              {isCameraOff ? <VideoOff className="w-6 h-6" /> : <Video className="w-6 h-6" />}
              <span className="text-xs">{isCameraOff ? 'Turn On' : 'Turn Off'}</span>
            </Button>
          </div>
        </div>

        {/* Device Selection */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-white mb-3">Device Settings</h3>
          
          {/* Microphone Selection */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-white/80">Microphone</label>
            <select
              value={selectedAudioInput}
              onChange={(e) => setSelectedAudioInput(e.target.value)}
              className="w-full p-2 rounded-md bg-white/10 border border-white/20 text-white text-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
            >
              {audioDevices.map((device) => (
                <option key={device.deviceId} value={device.deviceId} className="bg-slate-800">
                  {device.label}
                </option>
              ))}
            </select>
          </div>

          {/* Camera Selection */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-white/80">Camera</label>
            <select
              value={selectedVideoInput}
              onChange={(e) => setSelectedVideoInput(e.target.value)}
              className="w-full p-2 rounded-md bg-white/10 border border-white/20 text-white text-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
            >
              {videoDevices.map((device) => (
                <option key={device.deviceId} value={device.deviceId} className="bg-slate-800">
                  {device.label}
                </option>
              ))}
            </select>
          </div>

          {/* Speaker Selection */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-white/80">Speaker</label>
            <select
              value={selectedAudioOutput}
              onChange={(e) => setSelectedAudioOutput(e.target.value)}
              className="w-full p-2 rounded-md bg-white/10 border border-white/20 text-white text-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
            >
              {audioOutputDevices.map((device) => (
                <option key={device.deviceId} value={device.deviceId} className="bg-slate-800">
                  {device.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Audio & Video Quality */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-white mb-3">Quality Settings</h3>
          
          {/* Volume Control */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-white/80 flex items-center space-x-2">
                <Volume2 className="w-4 h-4" />
                <span>Volume</span>
              </label>
              <span className="text-sm text-white/60">{volume}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={volume}
              onChange={handleVolumeChange}
              className="w-full h-2 bg-white/20 rounded-lg appearance-none cursor-pointer slider"
            />
          </div>

          {/* Video Quality */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-white/80">Video Quality</label>
            <select
              value={videoQuality}
              onChange={(e) => setVideoQuality(e.target.value)}
              className="w-full p-2 rounded-md bg-white/10 border border-white/20 text-white text-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
            >
              <option value="480p" className="bg-slate-800">480p (Low)</option>
              <option value="720p" className="bg-slate-800">720p (Medium)</option>
              <option value="1080p" className="bg-slate-800">1080p (High)</option>
            </select>
          </div>
        </div>

        {/* Accessibility Settings */}
        <div className="space-y-4">
          <h3 className="text-lg font-semibold text-white mb-3">Accessibility</h3>
          
          <div className="space-y-3">
            <label className="flex items-center space-x-3 cursor-pointer">
              <input
                type="checkbox"
                checked={highContrast}
                onChange={(e) => setHighContrast(e.target.checked)}
                className="w-4 h-4 rounded border-white/20 bg-white/10 text-orange-500 focus:ring-orange-500 focus:ring-2"
              />
              <span className="text-sm text-white/80">High contrast mode</span>
            </label>
            
            <label className="flex items-center space-x-3 cursor-pointer">
              <input
                type="checkbox"
                checked={reducedMotion}
                onChange={(e) => setReducedMotion(e.target.checked)}
                className="w-4 h-4 rounded border-white/20 bg-white/10 text-orange-500 focus:ring-orange-500 focus:ring-2"
              />
              <span className="text-sm text-white/80">Reduce motion</span>
            </label>
            
            <label className="flex items-center space-x-3 cursor-pointer">
              <input
                type="checkbox"
                checked={showCaptions}
                onChange={(e) => setShowCaptions(e.target.checked)}
                className="w-4 h-4 rounded border-white/20 bg-white/10 text-orange-500 focus:ring-orange-500 focus:ring-2"
              />
              <span className="text-sm text-white/80">Show captions</span>
            </label>
          </div>
        </div>

        {/* Mobile Participants (only on mobile) */}
        <div className="lg:hidden space-y-4">
          <h3 className="text-lg font-semibold text-white mb-3">Meeting</h3>
          
          <Button
            variant="outline"
            className="w-full glass-button text-white hover:bg-white/15 h-12 flex items-center justify-center space-x-2"
          >
            <Users className="w-5 h-5" />
            <span>View Participants</span>
          </Button>
        </div>

        {/* Leave Meeting */}
        <div className="pt-4 border-t border-white/10">
          <Button
            onClick={handleLeaveMeeting}
            variant="outline"
            className="w-full bg-red-500/20 border-red-500/60 text-red-400 hover:bg-red-500/30 h-12 flex items-center justify-center space-x-2"
          >
            <LogOut className="w-5 h-5" />
            <span>Leave Meeting</span>
          </Button>
        </div>

        {/* Meeting Info */}
        <div className="pt-4 border-t border-white/10">
          <div className="text-center space-y-1">
            <p className="text-white/60 text-xs">Meeting ID</p>
            <p className="text-white text-sm font-mono bg-white/5 px-3 py-2 rounded-md border border-white/10">
              {roomId}
            </p>
          </div>
        </div>
      </div>
    </ScrollArea>
  );
};

export default SettingsTab;