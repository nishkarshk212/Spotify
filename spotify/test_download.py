import asyncio
import sys
from pathlib import Path

# Add the parent directory to sys.path to import spotify
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from spotify.core.youtube import YouTube

async def main():
    yt = YouTube()
    
    # Test search
    print("Testing search...")
    track = await yt.search("Never Gonna Give You Up", 123)
    print(f"Found track: {track}" if track else "No track found")
    
    if track:
        # Test download (audio only)
        print("\nTesting download (audio)...")
        file_path = await yt.download(track.id, video=False)
        print(f"Downloaded file: {file_path}" if file_path else "Download failed")

if __name__ == "__main__":
    asyncio.run(main())
