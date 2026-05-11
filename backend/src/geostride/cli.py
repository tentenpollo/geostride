import argparse
import asyncio
import json
import os
from pathlib import Path

from geostride.core.config import get_settings
from geostride.core.logging import configure_logging
from geostride.models import ExecuteRequest, Coordinate, VibeWeights
from geostride.services.graph_loader import GraphLoader
from geostride.services.execution_service import ExecutionService
from geostride.services.cost_functions import CostFunctionEngine
from geostride.services.vibe_engine import VibeEngine
from geostride.services.routing import RoutingService
from geostride.services.loop_generator import LoopGenerator

def main():
    parser = argparse.ArgumentParser(description="GeoStride CLI - Generate walking routes from the command line")
    parser.add_argument("--lat", type=float, required=True, help="Origin latitude")
    parser.add_argument("--lon", type=float, required=True, help="Origin longitude")
    parser.add_argument("--duration", type=int, default=30, help="Walk duration in minutes (default: 30)")
    parser.add_argument("--greenery", type=float, default=0.5, help="Greenery vibe (0-1, default: 0.5)")
    parser.add_argument("--safety", type=float, default=0.5, help="Safety vibe (0-1, default: 0.5)")
    parser.add_argument("--quietness", type=float, default=0.5, help="Introvert mode vibe (0-1, default: 0.5)")
    parser.add_argument("--liveliness", type=float, default=0.5, help="Extrovert mode vibe (0-1, default: 0.5)")
    parser.add_argument("--output", type=str, default="route.geojson", help="Output GeoJSON file")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()
    
    settings = get_settings()
    configure_logging(debug=args.debug)
    
    print(f"Initializing GeoStride for location ({args.lat}, {args.lon})...")
    
    loader = GraphLoader(settings.cache_dir)
    graph = loader.load_graph_by_point(args.lat, args.lon, dist_meters=3000)
    
    cost_engine = CostFunctionEngine(loader.amenities)
    vibe_engine = VibeEngine(loader.amenities)
    routing_service = RoutingService(graph, cost_engine, vibe_engine)
    loop_generator = LoopGenerator(graph, routing_service, cost_engine, vibe_engine)
    
    execution_service = ExecutionService(
        loader, graph, cost_engine, vibe_engine, routing_service, loop_generator
    )
    
    request = ExecuteRequest(
        origin=Coordinate(lat=args.lat, lon=args.lon),
        duration_minutes=args.duration,
        vibes=VibeWeights(
            greenery=args.greenery,
            introvert_mode=args.quietness,
            extrovert_mode=args.liveliness,
            safety_check=args.safety
        )
    )
    
    print("Generating route...")
    result = execution_service.execute(request)
    
    output_path = Path(args.output)
    with open(output_path, "w") as f:
        json.dump(result.geojson.model_dump(), f, indent=2)
        
    print(f"Success! Route saved to {output_path}")
    print(f"Distance: {result.metadata.distance_meters:.0f}m")
    print(f"Estimated time: {result.metadata.estimated_duration_minutes:.1f}m")
    print(f"Vibe Score: {result.metadata.vibe_score:.2f}")

if __name__ == "__main__":
    main()
