import React, { useState, useRef, useEffect } from 'react';
import { useWebSocket } from '../contexts/WebSocketContext';

function LayersPanel({ animations, onPlayAnimation, onUploadAnimation }) {
  // Original state
  const [weight, setWeight] = useState(1.0);
  const [interpolationDuration, setInterpolationDuration] = useState(2.0);
  const fileInputRef = useRef(null);
  
  // New state for layers
  const [layerMode, setLayerMode] = useState('dynamic'); // 'dynamic' or 'static'
  const [layers, setLayers] = useState([]);
  const [selectedLayerId, setSelectedLayerId] = useState(null);
  const [nextLayerId, setNextLayerId] = useState(1);
  
  // Use WebSocket context for real-time updates
  const { data: wsData, isConnected, connectionError } = useWebSocket();
  const layerStatus = wsData.active_animations || [];
  
  // Base layer initialization has been removed to prevent automatic creation
  // This ensures only animation layers created by button clicks will be displayed
  
  // Track layers that are being removed for animation
  const [removingLayers, setRemovingLayers] = useState([]);
  
  // Update layers based on WebSocket data
  useEffect(() => {
    if (!layerStatus) return;
    
    console.log("Received layer status from WebSocket:", layerStatus);
    
    // In dynamic mode, we need to fully sync with backend layers
    // This means adding new layers, updating existing ones, and removing those no longer active
    if (layerMode === 'dynamic') {
      if (layerStatus.length === 0) {
        // If no active layers in backend, clear frontend layers
        if (layers.length > 0) {
          console.log("Clearing all layers as backend reports no active layers");
          
          // Mark all layers for removal with animation
          const allLayerIds = layers.map(layer => layer.id);
          setRemovingLayers(allLayerIds);
          
          // Remove layers after animation completes
          setTimeout(() => {
            setLayers([]);
            setRemovingLayers([]);
          }, 1100); // Slightly longer than the CSS animation duration (1000ms)
        }
        return;
      }
      
      // Update UI layers based on the received data
      const updatedLayers = layerStatus.map((animStatus, index) => {
        // Try to find existing layer with this animation name
        const existingLayer = layers.find(layer => layer.animation === animStatus.name);
        
        if (existingLayer) {
          // Update existing layer
          return {
            ...existingLayer,
            weight: animStatus.weight
          };
        } else {
          // Create new layer for this animation
          return {
            id: nextLayerId + index,
            name: `Layer ${layers.length + index + 1}`,
            animation: animStatus.name,
            weight: animStatus.weight,
            isSelected: false
          };
        }
      });
      
      // Check if we need to remove layers that no longer exist in backend
      const activeAnimationNames = layerStatus.map(status => status.name);
      const layersToRemove = layers.filter(layer => 
        !activeAnimationNames.includes(layer.animation)
      );
      
      if (layersToRemove.length > 0 || updatedLayers.length !== layers.length) {
        console.log("Syncing layers with backend - some layers were added or removed");
        
        if (layersToRemove.length > 0) {
          // Mark layers for removal with animation
          const layerIdsToRemove = layersToRemove.map(layer => layer.id);
          setRemovingLayers(layerIdsToRemove);
          
          // Remove layers after animation completes
          setTimeout(() => {
            // Only update if there are changes in layers
            setLayers(updatedLayers);
            setRemovingLayers([]);
            
            // Update nextLayerId to be beyond the highest used ID
            if (updatedLayers.length > 0) {
              const highestId = Math.max(...updatedLayers.map(layer => layer.id), 0);
              setNextLayerId(highestId + 1);
            }
          }, 1100); // Slightly longer than the CSS animation duration (1000ms)
        } else {
          // Only update if there are new layers added
          setLayers(updatedLayers);
          
          // Update nextLayerId to be beyond the highest used ID
          if (updatedLayers.length > 0) {
            const highestId = Math.max(...updatedLayers.map(layer => layer.id), 0);
            setNextLayerId(highestId + 1);
          }
        }
      } else if (updatedLayers.length > 0) {
        // Check if any weights have changed
        const weightsChanged = updatedLayers.some((layer, idx) => 
          layer.weight !== layers[idx].weight
        );
        
        if (weightsChanged) {
          console.log("Updating layer weights from backend");
          setLayers(updatedLayers);
        }
      }
    } else {
      // In static mode, we only update existing layers but don't add/remove automatically
      if (layerStatus.length === 0 || layers.length === 0) return;
      
      // Update weights and statuses of existing layers
      const updatedLayers = [...layers];
      let hasChanges = false;
      
      for (let i = 0; i < updatedLayers.length; i++) {
        const layer = updatedLayers[i];
        const backendLayer = layerStatus.find(status => status.name === layer.animation);
        
        if (backendLayer && layer.weight !== backendLayer.weight) {
          updatedLayers[i] = {
            ...layer,
            weight: backendLayer.weight
          };
          hasChanges = true;
        }
      }
      
      if (hasChanges) {
        console.log("Updating static layer weights from backend");
        setLayers(updatedLayers);
      }
    }
  }, [layerStatus, layerMode, layers, nextLayerId]);
  
  // Layer management functions
  const addLayer = () => {
    // Use the current layer count + 1 for the layer name
    const layerNumber = layers.length + 1;
    
    const newLayer = {
      id: nextLayerId, // Keep unique IDs for internal tracking
      name: `Layer ${layerNumber}`, // Use layer count for display name
      animation: null,
      weight: 0.0,
      isSelected: false
    };
    
    setLayers([...layers, newLayer]);
    setNextLayerId(nextLayerId + 1);
    
    // Select the new layer
    setSelectedLayerId(newLayer.id);
  };
  
  // Update layer names when layers are added or removed
  const updateLayerNames = () => {
    console.log("Updating layer names");
    setLayers(prevLayers => {
      // Count non-base layers
      const nonBaseLayers = prevLayers.filter(layer => !layer.isBaseLayer);
      
      // Create a map to track the new names
      let regularLayerIndex = 1;
      
      return prevLayers.map(layer => {
        // Preserve the name of the base layer
        if (layer.isBaseLayer) {
          console.log("Preserving base layer name:", layer.name);
          return layer;
        }
        
        // For regular layers, use sequential numbering
        const newName = `Layer ${regularLayerIndex++}`;
        console.log(`Renaming layer ${layer.name} to ${newName}`);
        
        return {
          ...layer,
          name: newName
        };
      });
    });
  };
  
  // Call updateLayerNames whenever layers change
  useEffect(() => {
    if (layers.length > 0) {
      // Only update names if there's more than just the base layer
      if (layers.length > 1 || (layers.length === 1 && !layers[0].isBaseLayer)) {
        updateLayerNames();
      }
    }
  }, [layers.length]);
  
  const removeLayer = (layerId) => {
    // Find the layer
    const layer = layers.find(l => l.id === layerId);
    
    // Don't allow removing the base layer
    if (layer && layer.isBaseLayer) {
      console.log("Cannot remove base layer");
      return;
    }
    
    // If removing the selected layer, clear selection
    if (selectedLayerId === layerId) {
      setSelectedLayerId(null);
    }
    
    setLayers(layers.filter(layer => layer.id !== layerId));
  };
  
  const selectLayer = (layerId) => {
    setSelectedLayerId(layerId);
    
    // Update selection state in layers
    setLayers(layers.map(layer => ({
      ...layer,
      isSelected: layer.id === layerId
    })));
  };
  
  // Animation management
  const addAnimationToLayer = (layerId, animationName) => {
    setLayers(layers.map(layer => {
      if (layer.id === layerId) {
        return {
          ...layer,
          animation: animationName,
          weight: weight // Use current weight setting
        };
      }
      return layer;
    }));
    
    // Play the animation
    onPlayAnimation(animationName, weight, interpolationDuration);
  };
  
  // Animation transport controls
  const handlePlayAnimation = (animationName) => {
    onPlayAnimation(animationName, weight, interpolationDuration);
  };
  
  const handlePauseAnimation = (animationName) => {
    // Send a pause command to the backend
    fetch('/api/animation/pause', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        animation_name: animationName
      }),
    }).catch(error => console.error('Error pausing animation:', error));
  };
  
  const handleRewindAnimation = (animationName) => {
    // Send a rewind command to the backend
    fetch('/api/animation/rewind', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        animation_name: animationName
      }),
    }).catch(error => console.error('Error rewinding animation:', error));
  };
  
  const updateLayerWeight = (layerId, newWeight) => {
    // Find the layer
    const layer = layers.find(l => l.id === layerId);
    if (!layer || !layer.animation) return;
    
    // Update the layer weight
    setLayers(layers.map(l => {
      if (l.id === layerId) {
        return { ...l, weight: newWeight };
      }
      return l;
    }));
    
    // Play the animation with the new weight
    onPlayAnimation(layer.animation, newWeight, interpolationDuration);
  };
  
  // Handle animation click based on mode
  const handleAnimationClick = (animationName) => {
    if (layerMode === 'dynamic') {
      // In dynamic mode, create a new layer for the animation
      const newLayer = {
        id: nextLayerId,
        name: `Layer ${nextLayerId}`,
        animation: animationName,
        weight: weight,
        isSelected: false
      };
      
      setLayers([...layers, newLayer]);
      setNextLayerId(nextLayerId + 1);
      
      // Play the animation
      onPlayAnimation(animationName, weight, interpolationDuration);
    } else {
      // In static mode, add to selected layer if one exists
      if (selectedLayerId !== null) {
        addAnimationToLayer(selectedLayerId, animationName);
      } else {
        // If no layer is selected, just play the animation as before
        onPlayAnimation(animationName, weight, interpolationDuration);
      }
    }
  };
  
  // Original handlers
  const handleWeightChange = (e) => {
    setWeight(parseFloat(e.target.value));
  };

  const handleInterpolationDurationChange = (e) => {
    setInterpolationDuration(parseFloat(e.target.value));
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      onUploadAnimation(e.target.files[0]);
      // Reset the file input
      e.target.value = null;
    }
  };
  
  // Get animation weight from status
  const getAnimationWeight = (animationName) => {
    const animation = layerStatus.find(anim => anim.name === animationName);
    return animation ? animation.weight : 0;
  };
  
  // Render the timeline view
  const renderTimelineView = () => {
    return (
      <div className="timeline-container">
        {layers.map(layer => {
          // Find animation status for this layer
          const animationStatus = layer.animation ? 
            layerStatus.find(anim => anim.name === layer.animation) : null;
          
          // Calculate weight-based color (grey to accent color)
          const weight = animationStatus ? animationStatus.weight : 0;
          const weightColor = `rgba(76, 175, 80, ${weight})`;
          
          // Calculate playhead position based on current frame and total frames
          let playheadPosition = '0%';
          if (animationStatus && animationStatus.total_frames > 0) {
            const progress = (animationStatus.current_frame / animationStatus.total_frames) * 100;
            playheadPosition = `${progress}%`;
          }
          
          // Check if this layer is being removed
          const isRemoving = removingLayers.includes(layer.id);
          
          return (
            <div 
              key={layer.id} 
              className={`timeline-layer ${layer.isSelected ? 'selected' : ''} ${isRemoving ? 'removing' : ''}`}
              onClick={() => selectLayer(layer.id)}
            >
              <div className={`layer-header ${layer.isBaseLayer ? 'base-layer-header' : ''}`}>
                <span className="layer-name">{layer.name}</span>
                <div className="layer-header-controls">
                  {/* Transport controls - moved from clip to layer header */}
                  {layer.animation && (
                    <div className="layer-transport-controls">
                      <button 
                        className="transport-btn play-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          handlePlayAnimation(layer.animation);
                        }}
                        title="Play"
                      >
                        ▶
                      </button>
                      <button 
                        className="transport-btn pause-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          handlePauseAnimation(layer.animation);
                        }}
                        title="Pause"
                      >
                        ⏸
                      </button>
                      <button 
                        className="transport-btn rewind-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRewindAnimation(layer.animation);
                        }}
                        title="Rewind"
                      >
                        ⏮
                      </button>
                    </div>
                  )}
                  
                  {/* Only show remove button for non-base layers in static mode */}
                  {layerMode === 'static' && !layer.isBaseLayer && (
                    <button 
                      className="remove-layer-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeLayer(layer.id);
                      }}
                    >
                      ×
                    </button>
                  )}
                </div>
              </div>
              
              <div className="layer-track">
                {layer.animation && (
                  <div 
                    className="animation-clip"
                    style={{ backgroundColor: weightColor }}
                  >
                    
                    <span className="clip-name">{layer.animation}</span>
                    
                    {/* Weight display - only this triggers the weight dialog */}
                    <span 
                      className="clip-weight"
                      onClick={(e) => {
                        e.stopPropagation();
                        // Prompt for new weight
                        const currentWeight = animationStatus ? animationStatus.weight : weight;
                        const newWeight = prompt('Enter new weight (0.0-1.0):', currentWeight);
                        if (newWeight !== null) {
                          updateLayerWeight(layer.id, parseFloat(newWeight));
                        }
                      }}
                      title="Click to change weight"
                    >
                      {(animationStatus ? animationStatus.weight * 100 : weight * 100).toFixed(0)}%
                    </span>
                    
                    {/* Playhead */}
                    {animationStatus && animationStatus.is_playing && (
                      <div 
                        className="playhead"
                        style={{ left: playheadPosition }}
                      ></div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    );
  };
  
  // Render layer controls
  const renderLayerControls = () => {
    return (
      <div className="layer-controls">
        {layerMode === 'static' && (
          <button onClick={addLayer} className="add-layer-btn">
            + Add Layer
          </button>
        )}
      </div>
    );
  };

  return (
    <div className="panel">
      <h2>Animation Layers</h2>
      
      {/* Mode Toggle */}
      <div className="layer-mode-toggle">
        <label>
          Layer Mode:
          <select 
            value={layerMode} 
            onChange={(e) => setLayerMode(e.target.value)}
          >
            <option value="static">Static (Manual Layers)</option>
            <option value="dynamic">Dynamic (Auto Layers)</option>
          </select>
        </label>
        <p className="mode-description">
          {layerMode === 'dynamic' 
            ? 'Dynamic Mode: Layers are automatically created when animations are played and removed when complete.' 
            : 'Static Mode: Manually create layers and add animations to selected layers.'}
        </p>
      </div>
      
      {/* Layer Management */}
      {renderLayerControls()}
      
      {/* Timeline View */}
      {renderTimelineView()}
      
      {/* Original Controls */}
      <div className="control-settings">
        <div className="setting-group">
          <label htmlFor="weight">Animation weight:</label>
          <input
            id="weight"
            type="number"
            step="any"
            min="0.0"
            max="1.0"
            value={weight}
            onChange={handleWeightChange}
          />
        </div>
        
        <div className="setting-group">
          <label htmlFor="interpolation-duration">Interpolation duration (seconds):</label>
          <input
            id="interpolation-duration"
            type="number"
            step="any"
            min="0.0"
            value={interpolationDuration}
            onChange={handleInterpolationDurationChange}
          />
        </div>
      </div>
      
      <h3>Animations</h3>
      <div className="animation-list">
        {animations.map((animationName) => (
          <div key={animationName} className="animation-item">
            <button onClick={() => handleAnimationClick(animationName)}>
              {animationName}
            </button>
          </div>
        ))}
      </div>
      
      <div className="upload-section">
        <h3>Upload Animation</h3>
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

export default LayersPanel;
