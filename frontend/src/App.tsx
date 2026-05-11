import { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, GeoJSON, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { Moon, Sun, MapPin, Play, Activity } from 'lucide-react';

// Leaflet's default icon uses runtime require() for image paths, which Vite cannot resolve.
// The standard fix is to delete the default _getIconUrl and set explicit CDN URLs.
delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface VibeWeights {
  greenery: number;
  blue_space: number;
  introvert_mode: number;
  extrovert_mode: number;
  safety_check: number;
  walkability: number;
}

interface RouteData {
  success: boolean;
  geojson: {
    type: "FeatureCollection";
    features: {
      type: "Feature";
      geometry: {
        type: "LineString";
        coordinates: Array<[number, number]>;
      };
      properties: Record<string, unknown>;
    }[];
  };
  metadata: {
    distance_meters: number;
    estimated_duration_minutes: number;
    vibe_score: number;
    vibe_breakdown: Record<string, number>;
  };
  execution_details: {
    algorithm: string;
    nodes_explored: number;
    graph_size: string;
    disjoint_percentage: number;
    execution_time_ms: number;
  };
}

interface LocationMarkerProps {
  position: L.LatLng | null;
  setPosition: (pos: L.LatLng) => void;
}

const defaultVibes: VibeWeights = {
  greenery: 0.5,
  blue_space: 0.5,
  introvert_mode: 0.5,
  extrovert_mode: 0.5,
  safety_check: 0.5,
  walkability: 0.5,
};

function LocationMarker({ position, setPosition }: LocationMarkerProps) {
  useMapEvents({
    click(e) {
      setPosition(e.latlng);
    },
  });

  return position === null ? null : (
    <Marker position={position}>
      <Popup>Start here</Popup>
    </Marker>
  );
}

export default function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [position, setPosition] = useState<L.LatLng | null>(null);
  const [duration, setDuration] = useState(30);
  const [vibes, setVibes] = useState<VibeWeights>(defaultVibes);
  const [routeData, setRouteData] = useState<RouteData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (isDark) {
      setTheme('dark');
      document.documentElement.setAttribute('data-theme', 'dark');
    }
  }, []);

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
  };

  const handleVibeChange = (key: keyof VibeWeights, value: number) => {
    setVibes(prev => ({ ...prev, [key]: value }));
  };

  const generateRoute = async () => {
    if (!position) {
      setError('Please select a starting point on the map');
      setTimeout(() => setError(null), 3000);
      return;
    }

    setLoading(true);
    setRouteData(null);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          origin: { lat: position.lat, lon: position.lng },
          duration_minutes: duration,
          vibes: vibes
        })
      });

      const data: RouteData = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data ? 'Route generation failed' : 'Failed to generate route');
      }

      setRouteData(data);

      if (data.geojson && data.geojson.features.length > 0) {
        const coords = data.geojson.features[0].geometry.coordinates;
        const lats = coords.map((c: number[]) => c[1]);
        const lngs = coords.map((c: number[]) => c[0]);
        const centerLat = (Math.min(...lats) + Math.max(...lats)) / 2;
        const centerLng = (Math.min(...lngs) + Math.max(...lngs)) / 2;
        setPosition(new L.LatLng(centerLat, centerLng));
      }

    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setTimeout(() => setError(null), 5000);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      {error && (
        <div className="toast error">
          <span>{error}</span>
        </div>
      )}

      <div className="sidebar">
        <div className="header">
          <div className="header-title">
            <Activity size={24} color="var(--primary-color)" />
            <span>GeoStride</span>
          </div>
          <button className="theme-toggle" onClick={toggleTheme}>
            {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
          </button>
        </div>

        <div className="content">
          <div className="form-group">
            <label className="label">Target Duration (minutes)</label>
            <input
              type="range"
              className="slider"
              min="5"
              max="120"
              step="5"
              value={duration}
              onChange={(e) => setDuration(parseInt(e.target.value))}
            />
            <div style={{ textAlign: 'center', fontWeight: '500' }}>{duration} mins</div>
          </div>

          <div className="form-group">
            <label className="label">Route Preferences</label>
            <div className="slider-container">
              {Object.entries(vibes).map(([key, value]) => (
                <div key={key} className="slider-group">
                  <div className="slider-header">
                    <span>{key.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
                    <span>{Math.round(value * 100)}%</span>
                  </div>
                  <input
                    type="range"
                    className="slider"
                    min="0"
                    max="1"
                    step="0.1"
                    value={value}
                    onChange={(e) => handleVibeChange(key as keyof VibeWeights, parseFloat(e.target.value))}
                  />
                </div>
              ))}
            </div>
          </div>

          <button
            className="btn btn-primary"
            onClick={generateRoute}
            disabled={loading || !position}
          >
            {loading ? 'Generating...' : (
              <>
                <Play size={16} /> Generate Route
              </>
            )}
          </button>

          {routeData && (
            <div className="route-stats">
              <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Route Overview</h3>
              <div className="stat-grid">
                <div className="stat-item">
                  <span className="stat-value">{(routeData.metadata.distance_meters / 1000).toFixed(2)} km</span>
                  <span className="stat-label">Distance</span>
                </div>
                <div className="stat-item">
                  <span className="stat-value">{routeData.metadata.estimated_duration_minutes.toFixed(0)} min</span>
                  <span className="stat-label">Estimated Time</span>
                </div>
                <div className="stat-item">
                  <span className="stat-value">{Math.round(routeData.metadata.vibe_score * 100)}%</span>
                  <span className="stat-label">Vibe Match</span>
                </div>
                <div className="stat-item">
                  <span className="stat-value">{Math.round(routeData.execution_details.disjoint_percentage * 100)}%</span>
                  <span className="stat-label">Loop Novelty</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="map-container">
        {!position && (
          <div className="instruction-overlay">
            <MapPin size={18} /> Click anywhere on the map to set starting point
          </div>
        )}
        {loading && (
          <div className="loading-overlay">
            <div className="spinner"></div>
            <div style={{ fontWeight: 500 }}>Generating your perfect walk...</div>
          </div>
        )}
        <MapContainer
          center={[14.5547, 121.0244]}
          zoom={13}
          style={{ height: '100%', width: '100%', zIndex: 0 }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url={theme === 'dark'
              ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
              : 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
            }
          />
          <LocationMarker position={position} setPosition={setPosition} />

          {routeData && routeData.geojson && (
            <GeoJSON
              data={routeData.geojson}
              style={(feature) => ({
                color: feature?.properties?.stroke || '#22c55e',
                weight: feature?.properties?.['stroke-width'] || 5,
                opacity: feature?.properties?.['stroke-opacity'] || 0.8
              })}
            />
          )}
        </MapContainer>
      </div>
    </div>
  );
}
