# Copyright (c) 2025 TheHamkerAlone
# Licensed under the MIT License
# This file is part of spotifyMusic
# ALONE-CODE

import os
import re
import asyncio
import aiohttp
import random
import yt_dlp
from pathlib import Path
from py_yt import Playlist, VideosSearch
from spotify import logger, config
from spotify.helpers import Track, utils

DOWNLOAD_DIR = "downloads"

class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.api_url = config.ARUYT_API_URL
        self.api_key = config.ARUYT_API_KEY
        self.cookies = []
        self.checked = False
        # Get absolute path to cookies directory
        core_dir = Path(__file__).parent
        self.cookie_dir = str(core_dir.parent / "cookies")
        self.warned = False
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )

    def get_cookies(self):
        if not self.checked:
            if os.path.exists(self.cookie_dir):
                for file in os.listdir(self.cookie_dir):
                    if file.endswith(".txt"):
                        self.cookies.append(f"{self.cookie_dir}/{file}")
            self.checked = True
        if not self.cookies:
            if not self.warned:
                self.warned = True
                logger.warning("Cookies are missing; downloads might fail.")
            return None
        return random.choice(self.cookies)

    async def save_cookies(self, urls: list[str]) -> None:
        logger.info("Saving cookies from urls...")
        if not os.path.exists(self.cookie_dir):
            os.makedirs(self.cookie_dir)
        async with aiohttp.ClientSession() as session:
            for i, url in enumerate(urls):
                path = f"{self.cookie_dir}/cookie_{i}.txt"
                link = "https://batbin.me/api/v2/paste/" + url.split("/")[-1]
                async with session.get(link) as resp:
                    resp.raise_for_status()
                    with open(path, "wb") as fw:
                        fw.write(await resp.read())
        logger.info(f"Cookies saved in {self.cookie_dir}.")

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        _search = VideosSearch(query, limit=1, with_live=False)
        results = await _search.next()
        if results and results["result"]:
            data = results["result"][0]
            return Track(
                id=data.get("id"),
                channel_name=data.get("channel", {}).get("name"),
                duration=data.get("duration"),
                duration_sec=utils.to_seconds(data.get("duration")),
                message_id=m_id,
                title=data.get("title")[:25],
                thumbnail=data.get("thumbnails", [{}])[-1].get("url").split("?")[0],
                url=data.get("link"),
                view_count=data.get("viewCount", {}).get("short"),
                video=video,
            )
        return None

    async def playlist(self, limit: int, user: str, url: str, video: bool) -> list[Track | None]:
        tracks = []
        try:
            plist = await Playlist.get(url)
            for data in plist["videos"][:limit]:
                track = Track(
                    id=data.get("id"),
                    channel_name=data.get("channel", {}).get("name", ""),
                    duration=data.get("duration"),
                    duration_sec=utils.to_seconds(data.get("duration")),
                    title=data.get("title")[:25],
                    thumbnail=data.get("thumbnails")[-1].get("url").split("?")[0],
                    url=data.get("link").split("&list=")[0],
                    user=user,
                    view_count="",
                    video=video,
                )
                tracks.append(track)
        except:
            pass
        return tracks

    async def download(self, video_id: str, video: bool = False, chat_id: int = None) -> str | None:
        if not video_id or len(video_id) < 11:
            return None

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        ext = "mp4" if video else "mp3"
        file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")

        if os.path.exists(file_path):
            return file_path

        # Check played songs cache for fast replay
        if chat_id:
            from spotify import db
            cached_path = await db.get_played_song(chat_id, video_id)
            if cached_path and os.path.exists(cached_path):
                return cached_path

        # First try external API
        try:
            async with aiohttp.ClientSession() as session:
                params = {"url": video_id, "type": "video" if video else "audio", "api_key": self.api_key}
                async with session.get(
                    f"{self.api_url}/download",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    if response.status != 200:
                        raise Exception("API failed")
                    # Check if response is JSON or direct file
                    content_type = response.headers.get('Content-Type', '')
                    if 'application/json' in content_type:
                        data = await response.json()
                        token = data.get("download_token")
                        if not token:
                            raise Exception("No token")

                        stream_url = f"{self.api_url}/stream/{video_id}?type={'video' if video else 'audio'}&token={token}&api_key={self.api_key}"
                        async with session.get(
                            stream_url,
                            timeout=aiohttp.ClientTimeout(total=600 if video else 300),
                        ) as resp:
                            if resp.status == 302:
                                redirect_url = resp.headers.get('Location')
                                if redirect_url:
                                    async with session.get(redirect_url) as final_resp:
                                        if final_resp.status == 200:
                                            await self._write_file(file_path, final_resp)
                            elif resp.status == 200:
                                await self._write_file(file_path, resp)
                    else:
                        # Direct file download
                        await self._write_file(file_path, response)

                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    return file_path
        except Exception as e:
            logger.warning(f"External API download error: {e}, falling back to yt-dlp")

        # Fallback to yt-dlp
        try:
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
            cookie_file = self.get_cookies()
            
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best' if video else 'bestaudio/best',
                'outtmpl': file_path,
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
            }
            
            if not video:
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            
            if cookie_file:
                ydl_opts['cookiefile'] = cookie_file
            
            # Use to_thread to run yt-dlp in executor (since it's sync)
            def _download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([youtube_url])
            
            await asyncio.to_thread(_download)
            
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                return file_path
        except Exception as e:
            logger.error(f"yt-dlp fallback error: {e}")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
        return None

    async def _write_file(self, file_path, response):
        with open(file_path, "wb") as f:
            async for chunk in response.content.iter_chunked(16384):
                await asyncio.to_thread(f.write, chunk)
