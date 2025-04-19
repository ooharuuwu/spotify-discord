import discord
import spotipy
import lyricsgenius
from dotenv import load_dotenv
load_dotenv()

import os
from openai import OpenAI
from token_store import get_token


TOKEN = os.getenv("TOKEN")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GENIUS_API_TOKEN = os.getenv("GENIUS_API_TOKEN")

client = OpenAI(api_key=OPENAI_API_KEY)

token_scope = "user-read-playback-state user-modify-playback-state"

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = discord.Client(intents=intents)
genius = lyricsgenius.Genius(GENIUS_API_TOKEN)


def play_song(song_query, sp: spotipy.Spotify):
    if " by " in song_query:
        track_name, artist_name = song_query.split(" by ", 1)
    else:
        track_name = song_query
        artist_name = ""
    
    refined_query = (
        f"track:{track_name.strip()} artist:{artist_name.strip()}"
        if artist_name
        else track_name.strip()
    )

    max_query_length = 240
    if len(refined_query) > max_query_length:
        refined_query = refined_query[:max_query_length]

    results = sp.search(q=refined_query, type="track", limit=1)
    attempts = 0
    max_attempts = 5

    while not results["tracks"]["items"] and attempts < max_attempts:
        fallback_result = extract_random_with_gpt(text=song_query)
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
        return "No valid song found after multiple attempts. Please try again"
    
    track = results["tracks"]["items"][0]
    uri = track["uri"]
    devices = sp.devices()["devices"]

    if not devices:
        return "No active Spotify device found, please open spotfiy somewhere"
    
    device_id = devices[0]["id"]
    sp.start_playback(device_id=device_id, uris=[uri])

    return f"\U0001F3B5 Now playing: **{track['name']}** by **{track['artists'][0]['name']}**"


def extract_id_from_url(url, content_type):
    try:
        return url.split(f"{content_type}/")[1].split("?")[0]
    except IndexError:
        return None
    #incomplete

    
def play_spotify_link(url: str, sp: spotipy.Spotify):
    track_id = extract_id_from_url(url, "track")
    if not track_id:
        return "Invalid Spotify URL"
    
    track = sp.track(track_id)
    devices = sp.devices()["devices"]
    if not devices:
        return "No active Spotify device found, please open spotfiy somewhere"
    
    sp.start_playback(device_id=devices[0]["id"], uris=[track['uri']])
    return f"\U0001F3B5 Now playing: **{track['name']}** by **{track['artists'][0]['name']}**"


def play_album_link(url: str, sp: spotipy.Spotify):
    album_id = extract_id_from_url(url, "album")
    if not album_id:
        return "Invalid Spotify Album URL"
    
    devices = sp.devices()["devices"]
    if not devices:
        return "No active Spotify device found, please open spotfiy somewhere"
    
    sp.start_playback(device_id=devices[0]["id"], context_uri=f"spotify:album:{album_id}")
    return "🎵 Now playing album!"


def play_playlist_link(url:str, sp: spotipy.Spotify):
    playlist_id = extract_id_from_url(url, "playlist")
    if not playlist_id:
        return "Invalid Spotify playlist url"
    
    devices = sp.devices()["devices"]

    if not devices:
        return "No active Spotify device found, please open spotfiy somewhere"
    
    sp.start_playback(device_id=devices[0]["id"], context_uri=f"spotify:playlist:{playlist_id}")
    return "🎵 Now playing playlist!"


async def extract_song_from_reply(message):
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
            
            print(texts)
            return "\n".join(texts) if texts else None, source_type
    return None, "text"


def extract_text_from_image_url(image_url):
    response = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract the text from this image."},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ]
    )
    return response.choices[0].message.content


def extract_random_with_gpt(text):
    response = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[
            {"role": "system", "content": "You match vague song descriptions to actual track names and artists. Return in the format 'SONG_NAME by ARTIST'."},
            {"role": "user", "content": text}
        ]
    )
    return response.choices[0].message.content


def extract_song_artist_with_genius(text):
    query = " ".join(text.split())
    query = query if len(query) < 100 else query[:100]
    results = genius.search_songs(query)

    if results and "hits" in results and results['hits']:
        best_hit = results['hits'][0]['result']
        return f"{best_hit['title']} by {best_hit['primary_artist']['name']}"
    else:
        return None


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if "play this" in message.content.lower():

        #fetching the token info
        token_info = get_token(str(message.author.id))
        if not token_info:
            login_url = f"{os.getenv('OAUTH_SERVER_URL')}/login?user_id={message.author.id}"
            embed = discord.Embed(
                title="🎧 Connect your Spotify",
                description=f"[Click here to log in]({login_url}) to link your account.",
                color=0x1DB954
            )
            await message.author.send(embed=embed)
            return
        
        #creating spotify client with their access token
        sp = spotipy.Spotify(auth=token_info["access_token"])


        #getting thigns from replied message
        text_content, source = await extract_song_from_reply(message)

        if text_content is not None:
            if source == "spotify_link":
                response_msg = play_spotify_link(text_content, sp)
            elif source == "spotify_album":
                response_msg = play_album_link(text_content, sp)
            elif source == "spotify_playlist":
                response_msg = play_playlist_link(text_content, sp)
            elif source == "image":
                extracted_text = extract_text_from_image_url(text_content)
                print("Extracted lyrics:", extracted_text)
                song_info = extract_song_artist_with_genius(extracted_text)
                print("Extracted song info:", song_info)
                response_msg = play_song(song_info, sp)
            else:
                song_info = extract_random_with_gpt(text_content)
                if " by " not in song_info:
                    song_info = extract_song_artist_with_genius(text_content)
                print("Extracted song info:", song_info)
                response_msg = play_song(song_info, sp)

            await message.channel.send(response_msg)
        else:
            await message.channel.send("Couldn't find the song.")

bot.run(TOKEN)