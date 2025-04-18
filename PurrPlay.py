import discord
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests
import json
import lyricsgenius
from dotenv import load_dotenv
import os
import re
from openai import OpenAI

load_dotenv()

TOKEN = os.getenv("TOKEN")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GENIUS_API_TOKEN = os.getenv("GENIUS_API_TOKEN")

client = OpenAI(api_key=OPENAI_API_KEY)

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = discord.Client(intents=intents)
genius = lyricsgenius.Genius(GENIUS_API_TOKEN)


def get_spotify_access_token():
    url = "https://accounts.spotify.com/api/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": SPOTIFY_REFRESH_TOKEN,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET
    }
    response = requests.post(url, data=data)
    return response.json().get("access_token")


def extract_song_from_reply(message):
    if message.reference:
        replied_message = message.reference.resolved #resolved to fetch the replied to message
        if replied_message:
            texts = []
            source_type = "text"

            if replied_message.content:
                text = replied_message.content.strip()
                texts.append(text)

                if text.startswith("https://open.spotify.com/track"):
                    return text, "spotify_link"
                elif text.startswith("https://open.spotify.com/album"):
                    return text, "spotify_album"
                elif text.startswith("https://open.spotify.com/playlist"):
                    return text, "spotify_playlist"
            
            if replied_message.embeds:
                for embed in replied_message.embeds:
                    if embed.title:
                        texts.append(embed.title.strip())
                    if embed.description:
                        texts.append(embed.description.strip())
            
            if replied_message.attachments:
                for attachment in replied_message.attachments:
                    if attachment.content_type and attachment.content_type.startswith("image"):
                        image_url = attachment.url
                        source_type = "image"
                        return image_url, source_type
                    
            return "\n".join(texts) if texts else None, source_type
    return None, "text"

def extract_id_from_url(url, content_type):
    try:
        return url.split(f"{content_type}/")[1].split("?")[0]
    except IndexError:
        return None
    #incomplete

    
def play_spotify_link(url):
    track_id = extract_id_from_url(url, "track")
    if not track_id:
        return "Invalid Spotify URL"
    
    access_token = get_spotify_access_token()
    sp = spotipy.Spotify(auth=access_token)
    devices = sp.devices()["devices"]
    if not devices:
        return "No active Spotify device found, please open spotfiy somewhere"
    
    track = sp.track(track_id)
    sp.start_playback(device_id=devices[0]["id"], uris=[track['uri']])
    return f"\U0001F3B5 Now playing: **{track['name']}** by **{track['artists'][0]['name']}**"


def play_album_link(url):
    album_id = extract_id_from_url(url, "album")
    if not album_id:
        return "Invalid Spotify Album URL"
    
    access_token = get_spotify_access_token()
    sp = spotipy.Spotify(auth=access_token)
    devices = sp.devices()["devices"]

    if not devices:
        return "No active Spotify device found, please open spotfiy somewhere"
    
    sp.start_playback(device_id=devices[0]["id"], context_uri=f"spotify:album:{album_id}")


def play_playlist_link(url):
    playlist_id = extract_id_from_url(url, "playlist")
    if not playlist_id:
        return "Invalid Spotify playlist url"

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if "play this" in message.content.lower():
        text_content, source = await extract_song_from_reply(message)

        if text_content is not None:
            if source == "spotify_link":
                response_msg = play_spotify_link(text_content)
            if source 
