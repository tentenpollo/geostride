import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import App from './App';

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="map">{children}</div>
  ),
  TileLayer: () => <div data-testid="tile-layer" />,
  Marker: () => <div data-testid="marker" />,
  Popup: () => <div data-testid="popup" />,
  GeoJSON: () => <div data-testid="geojson" />,
  useMapEvents: () => {},
}));

describe('App', () => {
  it('renders the app title', () => {
    render(<App />);
    expect(screen.getByText('GeoStride')).toBeInTheDocument();
  });

  it('shows instruction overlay initially', () => {
    render(<App />);
    expect(screen.getByText(/Click anywhere on the map/i)).toBeInTheDocument();
  });

  it('renders duration slider', () => {
    render(<App />);
    expect(screen.getByText('Target Duration (minutes)')).toBeInTheDocument();
  });

  it('renders vibe sliders', () => {
    render(<App />);
    expect(screen.getByText('Route Preferences')).toBeInTheDocument();
  });

  it('generates a vibes slider label from key', () => {
    render(<App />);
    expect(screen.getByText('Greenery')).toBeInTheDocument();
    expect(screen.getByText('Blue Space')).toBeInTheDocument();
    expect(screen.getByText('Safety Check')).toBeInTheDocument();
  });

  it('toggles theme on button click', () => {
    render(<App />);
    const toggleButton = screen.getByRole('button', { name: '' });
    fireEvent.click(toggleButton);
  });
});
