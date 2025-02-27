import React, { useState, useRef } from 'react';

function LayersPanel({ animations, onPlayAnimation, onUploadAnimation }) {
  const [weight, setWeight] = useState(1.0);
  const [interpolationDuration, setInterpolationDuration] = useState(2.0);
  const fileInputRef = useRef(null);

  const handleWeightChange = (e) => {
    setWeight(parseFloat(e.target.value));
  };

  const handleInterpolationDurationChange = (e) => {
    setInterpolationDuration(parseFloat(e.target.value));
  };

  const handleAnimationClick = (animationName) => {
    onPlayAnimation(animationName, weight, interpolationDuration);
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      onUploadAnimation(e.target.files[0]);
      // Reset the file input
      e.target.value = null;
    }
  };

  return (
    <div className="panel">
      <h2>Animation Layers</h2>
      
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
