# Importing libraries and modules
import os
import re
import discord
import yt_dlp
import asyncio
from collections import deque
from discord.ext import commands
from discord import app_commands
from discord.ext import commands #discord help command addition
from dotenv import load_dotenv
import spotipy  # Spotify integration
from spotipy.oauth2 import SpotifyClientCredentials # Spotify function authentication declaration


# Environment variables for tokens and other sensitive data
load_dotenv("dc_env/.env")
TOKEN = os.getenv("DISCORD_TOKEN")

# Spotify credentials - Needed for spotify API to access track info
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET")
))

# Create the structure for queueing songs - Dictionary of queues
SONG_QUEUES = {}
DISCONNECT_TIMERS = {}
DISCONNECT_DELAY = 300 

async def search_ytdlp_async(query, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(query, download=False)
    
def get_source(audio_url, ffmpeg_options):
    return discord.FFmpegOpusAudio(
        audio_url,
        **ffmpeg_options,
        executable="bin\\ffmpeg\\ffmpeg.exe"
    )

# Setup of intents. Intents are permissions the bot has on the server
intents = discord.Intents.default()
intents.message_content = True

# Custom help command
class HelpCommand(commands.DefaultHelpCommand):
    async def send_bot_help(self, mapping):
        help_message = """
        **Ti commands exoumentes:**

        **/pekse link or name** - Pekse tragouthkia pou YOUTUBE/SPOTIFY
        Example: `/pekse kineziko rap`

        **/epomeno** - Pezi to epomeno tragoudoui

        **/pafsi** - Kamno sovaro break

        **/sinexise** - Sinexizo na pezo jino p epeza

        **/katharista** - Katharizw tin lista me ta tragoudouthkia

        **/fie** - Fefko pou to kanali afou en me thelis
        """
        channel = self.context.channel
        await channel.send(help_message)

# Bot setup with custom help command
bot = commands.Bot(command_prefix="!", intents=intents, help_command=HelpCommand())


# Bot ready-up code
@bot.event
async def on_ready():
    await bot.tree.sync()  # Make sure slash commands sync
    print(f"{bot.user} is online and ready!")

async def disconnect_after_delay(guild_id, voice_client, channel):
    await asyncio.sleep(DISCONNECT_DELAY)
    if guild_id in SONG_QUEUES and not SONG_QUEUES[guild_id]:
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()
            await channel.send("**Eskolasa**")
        if guild_id in DISCONNECT_TIMERS:
            del DISCONNECT_TIMERS[guild_id]

@bot.tree.command(name="pafsi", description="Pause the currently playing song.")
async def pause(interaction: discord.Interaction):
    guild_id_str = str(interaction.guild_id)
    if guild_id_str in DISCONNECT_TIMERS:
        DISCONNECT_TIMERS[guild_id_str].cancel()
        del DISCONNECT_TIMERS[guild_id_str]
    voice_client = interaction.guild.voice_client
    if voice_client is None:
        return await interaction.response.send_message("En ime mesto voice arfoui")
    if not voice_client.is_playing():
        return await interaction.response.send_message("En paizei tipote re chiakko")
    voice_client.pause()
    await interaction.response.send_message("Ekamame jai tin pafsi mas")

@bot.tree.command(name="sinexise", description="Etw piso re gare")
async def resume(interaction: discord.Interaction):
    guild_id_str = str(interaction.guild_id)
    if guild_id_str in DISCONNECT_TIMERS:
        DISCONNECT_TIMERS[guild_id_str].cancel()
        del DISCONNECT_TIMERS[guild_id_str]
    voice_client = interaction.guild.voice_client
    if voice_client is None:
        return await interaction.response.send_message("EN EIMAI SE KANALI AXRISTE")
    if not voice_client.is_paused():
        return await interaction.response.send_message("EN EIMAI PAUSED RE GIOTA")
    voice_client.resume()
    await interaction.response.send_message("Oti xorefko peze mou")

# Command to clear the queue
@bot.tree.command(name="katharista", description="Clear the song queue.")
async def clear_queue(interaction: discord.Interaction):
    guild_id_str = str(interaction.guild_id)
    if guild_id_str in DISCONNECT_TIMERS:
        DISCONNECT_TIMERS[guild_id_str].cancel()
        del DISCONNECT_TIMERS[guild_id_str]
    if guild_id_str in SONG_QUEUES:
        SONG_QUEUES[guild_id_str].clear()
        await interaction.response.send_message("Ekatharisa tin lista re chiakko")
    else:
        await interaction.response.send_message("En eshi tpt queue")

#command to disconnect the bot from the voice channel
@bot.tree.command(name="fie", description="Disconnect the bot from the voice channel.")
async def fie(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client

    if voice_client is None:
        return await interaction.response.send_message("Enje eimai poupote gia na me fiis re axriste")

    try:
        # First stop any ongoing playback
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()

        # Then disconnect
        await voice_client.disconnect()
        await interaction.response.send_message("Ethkiokseme o aplistos")
        guild_id_str = str(interaction.guild_id)
        if guild_id_str in DISCONNECT_TIMERS:
            del DISCONNECT_TIMERS[guild_id_str]
        if guild_id_str in SONG_QUEUES:
            del SONG_QUEUES[guild_id_str]
    except Exception as e:
        print(f"Error disconnecting: {e}")
        await interaction.response.send_message("Espasa")


#Functions for spotify
# Check if the input is a Spotify URL
def is_spotify_url(query):
    spotify_pattern = r"https?://open\.spotify\.com/track/[A-Za-z0-9]+"
    return re.match(spotify_pattern, query)

# Check if the input is a YouTube URL
def is_youtube_url(query):
    youtube_patterns = [
        r"https?://(?:www\.)?youtube\.com/watch\?v=[A-Za-z0-9_-]+",
        r"https?://(?:www\.)?youtu\.be/[A-Za-z0-9_-]+"
    ]
    return any(re.match(pattern, query) for pattern in youtube_patterns)

# Fetch song name from Spotify URL
def get_spotify_track_name(url):
    try:
        track_id = url.split("track/")[1].split("?")[0]
        track_info = sp.track(track_id)
        return f"{track_info['artists'][0]['name']} - {track_info['name']}"
    except Exception as e:
        print(f"Error fetching Spotify track: {e}")
        return None

def get_spotify_track_info(url):
    "Get detailed track info from Spotify URL"
    try:
        track_id = url.split("track/")[1].split("?")[0]
        track = sp.track(track_id)
        return {
            'title': track['name'],
            'artist': track['artists'][0]['name'],
            'is_explicit': track.get('explicit', False)
        }
    except Exception as e:
        print(f"Spotify error: {e}")
        return None



# Play Command
@bot.tree.command(name="pekse", description="Vale tipote na pezei")

@app_commands.describe(song_query="Spotify/YouTube URL or search query")

async def play(interaction: discord.Interaction, song_query: str):
    print(f"[/pekse] Command received with query: {song_query}")
    await interaction.response.defer()
    print(f"[/pekse] Interaction deferred.")
    guild_id_str = str(interaction.guild_id)
    if guild_id_str in DISCONNECT_TIMERS:
        print(f"[/pekse] Cancelling disconnect timer.")
        DISCONNECT_TIMERS[guild_id_str].cancel()
        del DISCONNECT_TIMERS[guild_id_str]
    try:
        print(f"[/pekse] Checking voice channel.")
        if not interaction.user.voice:
            print(f"[/pekse] User not in a voice channel.")
            return await interaction.followup.send("Enna prepi na ise mesto kanali re kelleji")
        print(f"[/pekse] Handling voice client.")
        voice_client = interaction.guild.voice_client

        if not voice_client:
            print(f"[/pekse] Connecting to voice channel.")
            voice_client = await interaction.user.voice.channel.connect()
            print(f"[/pekse] Connected to voice channel.")
        elif voice_client.channel != interaction.user.voice.channel:
            print(f"[/pekse] Moving to user's voice channel.")
            await voice_client.move_to(interaction.user.voice.channel)
            print(f"[/pekse] Moved to user's voice channel.")

        # YouTube DL options
        ydl_options = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "default_search": "ytsearch",
            "match_filter": lambda info: not any(
                word in info.get('title', '').lower()
                for word in ['clean', 'censored', 'radio edit']
            ),
        }

        print(f"[/pekse] Handling input query.")
        if is_spotify_url(song_query):
            print(f"[/pekse] Input is a Spotify URL.")
            track_info = get_spotify_track_info(song_query)
            if not track_info:
                print(f"[/pekse] Error fetching Spotify track info.")
                return await interaction.followup.send("Exw issue me to spotify re chiakko sasme")
            query = f"{track_info['artist']} - {track_info['title']} official audio"
            print(f"[/pekse] Spotify query: {query}")
        elif is_youtube_url(song_query):
            print(f"[/pekse] Input is a YouTube URL.")
            query = song_query
            ydl_options["default_search"] = None # Don't prepend ytsearch
        elif song_query.startswith("https://") or song_query.startswith("http://"):
            return await interaction.followup.send("Mono spotify i youtube links re poushtoui")
        else:
            query = f"ytsearch:{song_query}"
            print(f"[/pekse] YouTube search query: {query}")

        print(f"[/pekse] Searching with yt-dlp.")
        results = await search_ytdlp_async(query, ydl_options)
        tracks = results.get("entries", [])
        if not tracks:
            if "entries" in results and not results["entries"]:
                print(f"[/pekse] No tracks found for URL or search.")
                return await interaction.followup.send("En ivra tpt me afto to link i anazitisi")
            elif 'url' in results:
                # Handle direct URL extraction
                tracks = [results]
            else:
                print(f"[/pekse] No tracks found.")
                return await interaction.followup.send("En ivra tpt")

        first_track = tracks[0]
        audio_url = first_track["url"]
        title = first_track.get("title", "Untitled")
        print(f"[/pekse] Found track: {title} - URL: {audio_url}")

        guild_id = str(interaction.guild_id)
        if guild_id not in SONG_QUEUES:
            SONG_QUEUES[guild_id] = deque()
            print(f"[/pekse] Created new queue for guild {guild_id}.")

        SONG_QUEUES[guild_id].append((audio_url, title))
        print(f"[/pekse] Added '{title}' to the queue.")

        if voice_client.is_playing() or voice_client.is_paused():
            print(f"[/pekse] Bot is playing music or it's paused. Sending 'added to queue' message.")
            await interaction.followup.send(f"Empike mestin lista: **{title}**")
        else:
            print(f"[/pekse] Bot is not playing. Calling play_next_song.")
            await play_next_song(voice_client, guild_id, interaction.channel)
            # Send a follow-up message NOW that the first song is being processed
            await interaction.followup.send(f"**Twra pezw:** `{title}`")

    except Exception as e:
        print(f"[/pekse] Error in /pekse: {e}")
        await interaction.followup.send("Kati espase pale")

# Function to handle playing the next song
async def play_next_song(voice_client, guild_id, channel):
    print("Inside play_next_song")
    print(f"play_next_song - voice_client: {voice_client}, connected: {voice_client.is_connected() if voice_client else None}")
    print(f"play_next_song - SONG_QUEUES.get({guild_id}): {SONG_QUEUES.get(guild_id)}")
    try:
        if not voice_client or not voice_client.is_connected():
            print("play_next_song - Voice client not valid or not connected.")
            return

        if not SONG_QUEUES.get(guild_id):
            print("play_next_song - Song queue is empty. Starting disconnect timer.")
            if guild_id in DISCONNECT_TIMERS:
                DISCONNECT_TIMERS[guild_id].cancel()
            DISCONNECT_TIMERS[guild_id] = asyncio.create_task(disconnect_after_delay(guild_id, voice_client, channel))
            return

        audio_url, title = SONG_QUEUES[guild_id].popleft()
        print(f"play_next_song - Playing: {title} - URL: {audio_url}")
        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn -c:a libopus -b:a 96k",
        }
        source = get_source(audio_url, ffmpeg_options)

        def after_play(error):
            print("Inside after_play")
            if error:
                print(f"Playback error in after_play: {error}")
            try:
                asyncio.run_coroutine_threadsafe(
                    play_next_song(voice_client, guild_id, channel),
                    bot.loop
                )
            except Exception as e:
                print(f"Error in after_play calling play_next_song: {e}")

        # Start playback
        voice_client.play(source, after=after_play)
        print(f"play_next_song - Started playing: {title}")
        # REMOVED THE CHANNEL SEND HERE

    except discord.ClientException as e:
        print(f"Discord Client Exception in play_next_song: {e}")
        await channel.send("**Espasa eni Client Exception**")
    except Exception as e:
        print(f"General Error in play_next_song: {e}")
        await channel.send("**Espasa**")

@bot.tree.command(name="epomeno", description="Skips the current playing song")
async def skip(interaction: discord.Interaction):
    guild_id_str = str(interaction.guild_id)
    if guild_id_str in DISCONNECT_TIMERS:
        DISCONNECT_TIMERS[guild_id_str].cancel()
        del DISCONNECT_TIMERS[guild_id_str]
    voice_client = interaction.guild.voice_client

    if not voice_client or not voice_client.is_connected():
        return await interaction.response.send_message("En ime mesto kanali re chiakko")

    if not voice_client.is_playing():
        return await interaction.response.send_message("En eshi eshi kati na fiis")

    # Check if queue exists and has songs
    if not SONG_QUEUES.get(guild_id_str):
        return await interaction.response.send_message("En eshi alles mousikes na pezoun re chiakko")

    # Clean up current player
    if voice_client.is_playing():
        voice_client.stop()

    # Small delay to ensure clean transition
    await asyncio.sleep(0.5)

    # Get next song
    try:
        audio_url, title = SONG_QUEUES[guild_id_str].popleft()
    except IndexError:
        return await interaction.response.send_message("tora na valw to epomeno")

    ffmpeg_options = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn -c:a libopus -b:a 96k -loglevel warning",
    }

    try:
        source = get_source(audio_url, ffmpeg_options)

        def after_play(error):
            if error:
                print(f"Error playing {title}: {error}")
            asyncio.run_coroutine_threadsafe(
                play_next_song(voice_client, guild_id_str, interaction.channel),
                bot.loop
            )

        voice_client.play(source, after=after_play)
        await interaction.response.send_message(f"Fefko tountin mousiki. Allo pano: **{title}**")
    except Exception as e:
        print(f"Error in skip: {e}")
        await interaction.response.send_message("kati espasen dame")

# Run the bot
bot.run(TOKEN)
