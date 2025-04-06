import discord
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import requests
import json
from PIL import Image
import pytesseract
from io import BytesIO
import lyricsgenius
import os

TOKEN = os.getenv("TOKEN")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")
GEMINI = os.getenv("GEMINI")
GENIUS_API_TOKEN = os.getenv("GENIUS_API_TOKEN")

# Set up discord intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = discord.Client(intents=intents)

genius = lyricsgenius.Genius(GENIUS_API_TOKEN)


def get_spotify_access_token():
    """Refresh the Spotify access token."""
    url = "https://accounts.spotify.com/api/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": SPOTIFY_REFRESH_TOKEN,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET
    }
    response = requests.post(url, data=data)
    return response.json().get("access_token")


def play_song(song_query):
    """
    Search and play a song on Spotify using a refined search query.
    The song_query should be in the format "SONG_NAME by ARTIST".
    If no track is found, repeatedly use extract_random_with_gemini as a fallback
    until a valid song is found or a maximum number of attempts is reached.
    """
    # Attempt to split the query into track and artist.
    if " by " in song_query:
        track_name, artist_name = song_query.split(" by ", 1)
    else:
        track_name = song_query
        artist_name = ""
    
    # Build the refined query.
    refined_query = (
        f"track:{track_name.strip()} artist:{artist_name.strip()}"
        if artist_name
        else track_name.strip()
    )
    
    # Ensure the query does not exceed Spotify's maximum query length (250 characters).
    max_query_length = 240
    if len(refined_query) > max_query_length:
        refined_query = refined_query[:max_query_length]
    
    access_token = get_spotify_access_token()
    sp = spotipy.Spotify(auth=access_token)

    results = sp.search(q=refined_query, type="track", limit=1)
    attempts = 0
    max_attempts = 5

    while not results["tracks"]["items"] and attempts < max_attempts:
        fallback_result = extract_random_with_gemini(song_query)
        if " by " in fallback_result:
            track_name, artist_name = fallback_result.split(" by ", 1)
            refined_query = f"track:{track_name.strip()} artist:{artist_name.strip()}"
        else:
            refined_query = fallback_result.strip()
        

        if len(refined_query) > max_query_length:
            refined_query = refined_query[:max_query_length]
        
        results = sp.search(q=refined_query, type="track", limit=1)
        attempts += 1

    if not results["tracks"]["items"]:
        return "No valid song found after multiple attempts. Please try again with a different description."

    track_uri = results["tracks"]["items"][0]["uri"]
    devices = sp.devices()["devices"]
    if not devices:
        return "No active devices found. Please open Spotify on a device."

    device_id = devices[0]["id"]
    sp.start_playback(device_id=device_id, uris=[track_uri])

    track = results["tracks"]["items"][0]
    return f"🎵 Now playing: **{track['name']}** by **{track['artists'][0]['name']}**"


async def extract_song_from_reply(message):
    """
    Extract text from a replied message.
    Checks for text, embeds, and if an image is present it uses OCR.
    Returns a tuple (extracted_text, source_type) where source_type is either "image" or "text".
    """
    if message.reference:
        replied_message = message.reference.resolved
        if replied_message:
            texts = []
            source_type = "text"
            if replied_message.content:
                texts.append(replied_message.content.strip())
            if replied_message.embeds:
                for embed in replied_message.embeds:
                    if embed.title:
                        texts.append(embed.title.strip())
                    if embed.description:
                        texts.append(embed.description.strip())
            if replied_message.attachments:
                for attachment in replied_message.attachments:
                    if attachment.content_type and attachment.content_type.startswith("image"):
                        source_type = "image"
                        image_bytes = await attachment.read()
                        image = Image.open(BytesIO(image_bytes))
                        ocr_text = pytesseract.image_to_string(image)
                        print("OCR output:", ocr_text)
                        texts.append(ocr_text.strip())
            return "\n".join(texts) if texts else None, source_type
    return None, "text"


def extract_song_artist_with_gemini(text):
    prompt = (f"Extract the song name and artist from the following text. "
              f"Return the result in the format 'SONG_NAME by ARTIST':\n\n{text}")    
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        response_data = response.json()
        return response_data["candidates"][0]["content"]["parts"][0]["text"]
    else:
        return "Something went wrong! 😿"


def 


def extract_random_with_gemini(text):
    prompt = (f"Find the song matching the text's description. "
              f"Return the result in the format 'SONG_NAME by ARTIST':\n\n{text}")    
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        response_data = response.json()
        return response_data["candidates"][0]["content"]["parts"][0]["text"]
    else:
        return "Something went wrong! 😿"


def extract_song_artist_with_genius(text):
    # Remove line breaks and extra spaces.
    query = " ".join(text.split())
    query = query if len(query) < 100 else query[:100]
    results = genius.search_songs(query)
    
    if results and 'hits' in results and results['hits']:
        best_hit = results['hits'][0]['result']
        return f"{best_hit['title']} by {best_hit['primary_artist']['name']}"
    else:
        return None


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')


@bot.event
async def on_message(message):
    """
    When a user sends a message with "play this", the bot checks if the message
    is a reply. It then extracts the referenced message text, passes it to Gemini
    for extracting song name and artist, and finally plays the song on Spotify.
    """
    if message.author == bot.user:
        return

    if "play this" in message.content.lower():
        text_content, source = await extract_song_from_reply(message)
        if text_content:
            # Use Gemini to extract the song info in the desired format.
            if source == "image":
                song_info = extract_song_artist_with_genius(text_content)
            else:
                song_info = extract_song_artist_with_gemini(text_content)

            print("Extracted song info:", song_info)

            if song_info and " by " in song_info:
                response_msg = play_song(song_info)
                await message.channel.send(response_msg)
            else:
                await message.channel.send("Could not extract valid song info. Please try again.")
        else:
            await message.channel.send("Couldn't find a song in the replied message.")
            
    if "max volume" in message.content.lower():
        access_token = get_spotify_access_token()
        sp = spotipy.Spotify(auth=access_token)
        devices = sp.devices()["devices"]
        if devices:
            device_id = devices[0]["id"]
            sp.volume(100, device_id=device_id)
            await message.channel.send("Volume set to maximum!")
        else:
            await message.channel.send("No active device found. Please open Spotify on a device.")


bot.run(TOKEN)