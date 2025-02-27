import React, { useState, useRef } from 'react';

function PlaylistsPanel({ playlists, playlistTransportPlaying, onPlaylistAction, onUploadPlaylist }) {
  const [selectedPlaylist, setSelectedPlaylist] = useState('');
  const fileInputRef = useRef(null);

  const handlePlaylistChange = (e) => {
    setSelectedPlaylist(e.target.value);
  };

  const handlePlaylistPlay = () => {
    if (selectedPlaylist) {
      onPlaylistAction(selectedPlaylist, 'play');
    }
  };

  const handlePlaylistStop = () => {
    if (selectedPlaylist) {
      onPlaylistAction(selectedPlaylist, 'stop');
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      onUploadPlaylist(e.target.files[0]);
      // Reset the file input
      e.target.value = null;
    }
  };

  return (
    <div className="panel">
      <h2>Playlists</h2>
      
      <div className="playlist-controls">
        <div className="playlist-selector">
          <label htmlFor="playlist-select">Choose playlist:</label>
          <select
            id="playlist-select"
            value={selectedPlaylist}
            onChange={handlePlaylistChange}
          >
            <option value="">Select a playlist</option>
            {playlists.map((playlist) => (
              <option key={playlist} value={playlist}>
                {playlist}
              </option>
            ))}
          </select>
        </div>
        
        <div className="playlist-transport">
          {playlistTransportPlaying ? (
            <button onClick={() => onPlaylistAction(selectedPlaylist, 'pause')} disabled={!selectedPlaylist}>
              Pause
            </button>
          ) : (
            <button onClick={handlePlaylistPlay} disabled={!selectedPlaylist}>
              Play
            </button>
          )}
          
          <button onClick={handlePlaylistStop} disabled={!selectedPlaylist}>
            Stop
          </button>
        </div>
      </div>
      
      <div className="upload-section">
        <h3>Upload Playlist</h3>
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept=".json"
        />
        <button onClick={() => fileInputRef.current.click()}>
          Choose File
        </button>
      </div>
    </div>
  );
}

export default PlaylistsPanel;
