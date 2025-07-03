import React, { useState, useEffect } from 'react';
import TransportPanel from './components/TransportPanel';
import PowerPanel from './components/PowerPanel';
import LayersPanel from './components/LayersPanel';
import PlaylistsPanel from './components/PlaylistsPanel';
import IOPanel from './components/IOPanel';
import StatusIndicator from './components/StatusIndicator';

function App() {
  const [activeTab, setActiveTab] = useState('transport');
  const [animations, setAnimations] = useState([]);
  const [playlists, setPlaylists] = useState([]);
  const [globalFramerate, setGlobalFramerate] = useState(30);
  const [transportPlaying, setTransportPlaying] = useState(false);
  const [playlistTransportPlaying, setPlaylistTransportPlaying] = useState(false);
  const [animationMode, setAnimationMode] = useState('transport');
  const [status, setStatus] = useState({ type: 'info', message: 'Ready' });

  // Fetch animations and playlists on component mount
  useEffect(() => {
    fetchAnimations();
    fetchPlaylists();
  }, []);

  const fetchAnimations = async () => {
    try {
      const response = await fetch('/api/animations');
      const data = await response.json();
      setAnimations(data.animations);
      setGlobalFramerate(data.global_framerate);
      setTransportPlaying(data.transport_playing);
      setAnimationMode(data.animation_mode);
    } catch (error) {
      setStatus({
        type: 'error',
        message: `Failed to fetch animations: ${error.message}`
      });
    }
  };

  const fetchPlaylists = async () => {
    try {
      const response = await fetch('/api/playlists');
      const data = await response.json();
      setPlaylists(data.playlists);
      setPlaylistTransportPlaying(data.playlist_transport_playing);
    } catch (error) {
      setStatus({
        type: 'error',
        message: `Failed to fetch playlists: ${error.message}`
      });
    }
  };

  const handleTransportAction = async (action, framerate) => {
    try {
      const response = await fetch('/api/transport', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          transport: action,
          global_framerate: framerate || globalFramerate
        }),
      });
      
      const data = await response.json();
      
      if (data.success) {
        setTransportPlaying(data.transport_playing);
        setGlobalFramerate(data.global_framerate);
        setStatus({
          type: 'success',
          message: `Transport ${action} successful`
        });
      } else {
        setStatus({
          type: 'error',
          message: data.error || 'Transport action failed'
        });
      }
    } catch (error) {
      setStatus({
        type: 'error',
        message: `Transport action failed: ${error.message}`
      });
    }
  };

  const handlePlayAnimation = async (animationName, weight, interpolationDuration) => {
    try {
      const response = await fetch('/api/animation/play', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          animation_name: animationName,
          weight: weight,
          interpolation_duration: interpolationDuration
        }),
      });
      
      const data = await response.json();
      
      if (data.success) {
        setStatus({
          type: 'success',
          message: `Playing animation: ${animationName}`
        });
      } else {
        setStatus({
          type: 'error',
          message: data.error || 'Failed to play animation'
        });
      }
    } catch (error) {
      setStatus({
        type: 'error',
        message: `Failed to play animation: ${error.message}`
      });
    }
  };

  const handlePlaylistAction = async (playlistName, action) => {
    try {
      const response = await fetch('/api/playlist/transport', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          playlist_name: playlistName,
          transport: action
        }),
      });
      
      const data = await response.json();
      
      if (data.success) {
        setStatus({
          type: 'success',
          message: `Playlist ${action}: ${playlistName}`
        });
        // Update animation mode if playing a playlist
        if (action === 'play') {
          setAnimationMode('playlist');
        } else if (action === 'stop') {
          setAnimationMode('transport');
        }
      } else {
        setStatus({
          type: 'error',
          message: data.error || 'Playlist action failed'
        });
      }
    } catch (error) {
      setStatus({
        type: 'error',
        message: `Playlist action failed: ${error.message}`
      });
    }
  };

  const handlePowerOff = async () => {
    try {
      const response = await fetch('/api/poweroff', {
        method: 'POST',
      });
      
      const data = await response.json();
      
      if (data.success) {
        setStatus({
          type: 'info',
          message: 'Power off initiated'
        });
      } else {
        setStatus({
          type: 'error',
          message: data.error || 'Power off failed'
        });
      }
    } catch (error) {
      setStatus({
        type: 'error',
        message: `Power off failed: ${error.message}`
      });
    }
  };

  const handleFileUpload = async (endpoint, file) => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await fetch(`/api/${endpoint}/add`, {
        method: 'POST',
        body: formData,
      });
      
      const data = await response.json();
      
      if (data.success) {
        setStatus({
          type: 'success',
          message: data.message
        });
        
        // Refresh animations or playlists list
        if (endpoint === 'animation') {
          fetchAnimations();
        } else if (endpoint === 'playlist') {
          fetchPlaylists();
        }
      } else {
        setStatus({
          type: 'error',
          message: data.error || 'Upload failed'
        });
      }
    } catch (error) {
      setStatus({
        type: 'error',
        message: `Upload failed: ${error.message}`
      });
    }
  };

  return (
    <div className="container">
      <h1>Animation Controller</h1>
      
      <div className="tabs">
        <div className="tab-buttons">
          <button 
            className={activeTab === 'transport' ? 'active' : ''} 
            onClick={() => setActiveTab('transport')}
          >
            Transport
          </button>
          <button 
            className={activeTab === 'power' ? 'active' : ''} 
            onClick={() => setActiveTab('power')}
          >
            Power
          </button>
          <button 
            className={activeTab === 'layers' ? 'active' : ''} 
            onClick={() => setActiveTab('layers')}
          >
            Layers
          </button>
          <button 
            className={activeTab === 'playlists' ? 'active' : ''} 
            onClick={() => setActiveTab('playlists')}
          >
            Playlists
          </button>
          <button 
            className={activeTab === 'camera' ? 'active' : ''} 
            onClick={() => setActiveTab('camera')}
          >
            IO
          </button>
        </div>
        
        <div className="tab-content">
          {activeTab === 'transport' && (
            <TransportPanel 
              transportPlaying={transportPlaying}
              globalFramerate={globalFramerate}
              animationMode={animationMode}
              onTransportAction={handleTransportAction}
            />
          )}
          
          {activeTab === 'power' && (
            <PowerPanel onPowerOff={handlePowerOff} />
          )}
          
          {activeTab === 'layers' && (
            <LayersPanel 
              animations={animations}
              onPlayAnimation={handlePlayAnimation}
              onUploadAnimation={(file) => handleFileUpload('animation', file)}
            />
          )}
          
          {activeTab === 'playlists' && (
            <PlaylistsPanel 
              playlists={playlists}
              playlistTransportPlaying={playlistTransportPlaying}
              onPlaylistAction={handlePlaylistAction}
              onUploadPlaylist={(file) => handleFileUpload('playlist', file)}
            />
          )}
          
          {activeTab === 'camera' && (
            <IOPanel 
              onStatusUpdate={setStatus}
            />
          )}
        </div>
      </div>
      
      <StatusIndicator type={status.type} message={status.message} />
    </div>
  );
}

export default App;
