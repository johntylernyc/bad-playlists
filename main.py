"""
Prerequisites

    pip3 install spotipy Flask Flask-Session

    // from your [app settings](https://developer.spotify.com/dashboard/applications)
    export SPOTIPY_CLIENT_ID=client_id_here
    export SPOTIPY_CLIENT_SECRET=client_secret_here
    export SPOTIPY_REDIRECT_URI='http://127.0.0.1:8080' // must contain a port
    // SPOTIPY_REDIRECT_URI must be added to your [app settings](https://developer.spotify.com/dashboard/applications)
    OPTIONAL
    // in development environment for debug output
    export FLASK_ENV=development
    // so that you can invoke the app outside of the file's directory include
    export FLASK_APP=/path/to/spotipy/examples/app.py

    // on Windows, use `SET` instead of `export`

Run app.py

    python3 app.py OR python3 -m flask run
    NOTE: If receiving "port already in use" error, try other ports: 5000, 8090, 8888, etc...
        (will need to be updated in your Spotify app and SPOTIPY_REDIRECT_URI variable)
"""

import os
from flask import Flask, session, request, redirect, jsonify, render_template, flash
from flask_session import Session
import spotipy
import urllib.parse
from urllib.parse import urlparse
from google.cloud import firestore
from helper_functions import generate_navigation
from random import sample
import random

app = Flask(__name__, template_folder='templates')
SPOTIPY_CLIENT_ID = os.environ.get('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.environ.get('SPOTIPY_CLIENT_SECRET')
SPOTIPY_REDIRECT_URI = os.environ.get('SPOTIPY_REDIRECT_URI')
FLASK_SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')
app.config['SESSION_TYPE'] = 'cookie'  # Use cookie-based sessions
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = '/tmp'
Session(app)

encoded_redirect_uri = urllib.parse.quote(SPOTIPY_REDIRECT_URI)
db = firestore.Client()
scope = [
    'user-read-currently-playing',
    'user-top-read',
    'app-remote-control',
    'user-modify-playback-state',
    'user-library-modify',
    'user-library-read',
    'user-read-playback-state',
    'user-modify-playback-state',
    'playlist-modify-public',
    'playlist-modify-private'
]


@app.route('/')
def index():

    cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(scope=scope,
                                               cache_handler=cache_handler,
                                               redirect_uri=SPOTIPY_REDIRECT_URI,
                                               show_dialog=True)

    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        # Step 1. Display sign in link when no token
        return '<a href="/login_with_spotify">Login with Spotify</a>'

    # Step 3. Signed in, display data
    spotify = spotipy.Spotify(auth_manager=auth_manager)
    navigation = generate_navigation(spotify)

    return navigation


@app.route('/callback')
def callback():
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        print(f"Error received from Spotify: {error}")
        return f"Error received from Spotify: {error}", 400
    elif code:
        print(f"Authorization code received: {code}")
        cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
        auth_manager = spotipy.oauth2.SpotifyOAuth(
            scope=scope,
            cache_handler=cache_handler,  # use custom cache handler
            redirect_uri=SPOTIPY_REDIRECT_URI,
            show_dialog=False
        )
        # Exchange the authorization code for an access token
        token_info = auth_manager.get_access_token(code)
        print(f"Token info received: {token_info}")
        # Save the token in the session
        session['token_info'] = token_info
        return redirect('/')
    else:
        return "Error: no code provided by Spotify callback.", 400


@app.route('/login_with_spotify')
def login_with_spotify():
    cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(scope=scope,
                                               cache_handler=cache_handler,
                                               redirect_uri=SPOTIPY_REDIRECT_URI,
                                               show_dialog=False)
    auth_url = auth_manager.get_authorize_url()
    return redirect(auth_url)


@app.route('/sign_out')
def sign_out():
    session.pop("token_info", None)
    session.clear()
    return redirect('/')


from flask import render_template

@app.route('/playlists')
def playlists():
    cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_handler=cache_handler)
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        return redirect('/')

    spotify = spotipy.Spotify(auth_manager=auth_manager)
    raw_playlists = spotify.current_user_playlists()["items"]

    formatted_playlists = []
    for raw_playlist in raw_playlists:
        formatted_playlist = {
            "name": raw_playlist["name"],
            "image_url": raw_playlist["images"][0]["url"] if raw_playlist["images"] else None,
            "num_tracks": raw_playlist["tracks"]["total"],
            }
        formatted_playlists.append(formatted_playlist)

    navigation = generate_navigation(spotify)
    return navigation + render_template('playlists.html', playlists=formatted_playlists, navigation=navigation)



@app.route('/currently_playing')
def currently_playing():
    cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_handler=cache_handler)
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        return redirect('/')
    spotify = spotipy.Spotify(auth_manager=auth_manager)
    track = spotify.current_user_playing_track()
    navigation = generate_navigation(spotify)
    scripts = """
     <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
     <script src="/static/playback.js"></script>
     """

    if track is not None:
        artist_id = track['item']['artists'][0]['id']
        top_tracks = spotify.artist_top_tracks(artist_id, country='US')['tracks']

        # Create an output string
        output = navigation

        # Add album art
        album_art_url = track['item']['album']['images'][0]['url']
        output += f'<img src="{album_art_url}" alt="Album Art" width="200"><br>'

        # Display currently playing track metadata
        output += f"<h3>Currently Playing:</h3> {track['item']['name']} by {track['item']['artists'][0]['name']}<br>"

        # Display top 10 tracks by the artist with clickable links
        output += "<h3>Top 10 Tracks by the Artist:</h3>"
        for i, song in enumerate(top_tracks[:10]):
            output += f'<a href="#" onclick="playTrack(\'{song["uri"]}\')">{i + 1}. {song["name"]}</a><br>'

        return output + scripts

    else:
        return navigation + "No track currently playing."


@app.route('/current_user')
def current_user():
    cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_handler=cache_handler)
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        return redirect('/')
    spotify = spotipy.Spotify(auth_manager=auth_manager)
    navigation = generate_navigation(spotify)
    user_data = spotify.current_user()

    # Extract relevant data fields
    display_name = user_data.get("display_name")
    followers_count = user_data.get("followers", {}).get("total")
    external_url = user_data.get("external_urls", {}).get("spotify")
    country = user_data.get("country")
    email = user_data.get("email")
    product = user_data.get("product")

    return navigation + render_template(
        'current_user.html',
        display_name=display_name,
        followers_count=followers_count,
        external_url=external_url,
        country=country,
        email=email,
        product=product,
        navigation=navigation
    )


@app.route('/top_tracks')
def top_tracks():
    cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_handler=cache_handler)
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        return redirect('/')

    spotify = spotipy.Spotify(auth_manager=auth_manager)
    ranges = ['short_term', 'medium_term', 'long_term']

    navigation = generate_navigation(spotify)

    save_button = '''
    <form action="javascript:void(0);" method="post">
        <input type="submit" id="save-button" value="Save Top Tracks">
        <span id="save-status"></span>
    </form>
    '''

    output = ""

    output += navigation

    output += save_button

    # Add the JavaScript to the output
    output += '''
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script>
    $(document).ready(function() {
        $("#save-button").click(function() {
            // Disable the button and show "Saving..."
            $("#save-button").prop("disabled", true);
            $("#save-status").text("Saving...");

            // Make an AJAX call to save the top tracks
            $.post("/save_top_tracks", function(data) {
                // When successful, show "Saved!"
                if (data.success) {
                    $("#save-status").text("Saved!");
                } else {
                    $("#save-status").text("Error: " + data.message);
                    $("#save-button").prop("disabled", false);
                }
            });
        });
    });
    </script>
    '''

    for sp_range in ranges:
        output += f"<h2>Range: {sp_range}</h2>"
        results = spotify.current_user_top_tracks(time_range=sp_range, limit=50)  # Note: Change `ranges` to `sp_range`
        for i, item in enumerate(results['items']):
            output += f"{i}. {item['name']} - {item['artists'][0]['name']}<br>"

    return output


@app.route('/save_top_tracks', methods=['POST'])
def save_top_tracks():
    try:
        cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
        auth_manager = spotipy.oauth2.SpotifyOAuth(cache_handler=cache_handler)
        if not auth_manager.validate_token(cache_handler.get_cached_token()):
            return redirect('/')

        spotify = spotipy.Spotify(auth_manager=auth_manager)
        ranges = ['short_term', 'medium_term', 'long_term']

        user_id = spotify.me()["id"]
        user_favorites_ref = db.collection('users').document(user_id).collection('user_favorites').document('top_tracks')

        all_tracks_data = []

        # Store the top tracks in Firestore
        for sp_range in ranges:
            results = spotify.current_user_top_tracks(time_range=sp_range, limit=50)
            for item in results['items']:
                track_data = {
                    'name': item['name'],
                    'artist': item['artists'][0]['name'],
                    'range': sp_range,
                    'album': item['album']['name'],
                    'track_id': item['id'],
                    'external_url': item['external_urls']['spotify'],
                    'image_url': item['album']['images'][0]['url'] if item['album']['images'] else None
                }
                all_tracks_data.append(track_data)

        user_favorites_ref.set({'tracks': all_tracks_data})
        return jsonify(success=True, message="Top tracks saved successfully!")
    except Exception as e:
        return jsonify(success=False, message=str(e))


@app.route('/top_artists')
def top_artists():
    cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_handler=cache_handler)
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        return redirect('/')

    spotify = spotipy.Spotify(auth_manager=auth_manager)
    ranges = ['short_term', 'medium_term', 'long_term']

    navigation = generate_navigation(spotify)

    save_button = '''
    <form action="javascript:void(0);" method="post">
        <input type="submit" id="save-button" value="Save Top Artists">
        <span id="save-status"></span>
    </form>
    '''

    output = ""

    output += navigation

    output += save_button

    # Add the JavaScript to the output
    output += '''
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script>
    $(document).ready(function() {
        $("#save-button").click(function() {
            // Disable the button and show "Saving..."
            $("#save-button").prop("disabled", true);
            $("#save-status").text("Saving...");

            // Make an AJAX call to save the top artists
            $.post("/save_top_artists", function(data) {
                // When successful, show "Saved!"
                if (data.success) {
                    $("#save-status").text("Saved!");
                } else {
                    $("#save-status").text("Error: " + data.message);
                    $("#save-button").prop("disabled", false);
                }
            });
        });
    });
    </script>
    '''

    for sp_range in ranges:
        output += f"<h2>Range: {sp_range}</h2>"
        results = spotify.current_user_top_artists(time_range=sp_range, limit=50)
        for i, item in enumerate(results['items']):
            output += f"{i}. {item['name']}<br>"

    return output


@app.route('/save_top_artists', methods=['POST'])
def save_top_artists():
    try:
        cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
        auth_manager = spotipy.oauth2.SpotifyOAuth(cache_handler=cache_handler)
        if not auth_manager.validate_token(cache_handler.get_cached_token()):
            return redirect('/')

        spotify = spotipy.Spotify(auth_manager=auth_manager)
        ranges = ['short_term', 'medium_term', 'long_term']

        user_id = spotify.me()["id"]
        user_favorites_ref = db.collection('users').document(user_id).collection('user_favorites').document('top_artists')

        all_artists_data = []

        # Store the top artists in Firestore
        for sp_range in ranges:
            results = spotify.current_user_top_artists(time_range=sp_range, limit=50)
            for item in results['items']:
                artist_data = {
                    'name': item['name'],
                    'range': sp_range,
                    'popularity': item['popularity'],
                    'external_url': item['external_urls']['spotify'],
                    'id': item['id']
                }
                all_artists_data.append(artist_data)

        user_favorites_ref.set({'artists': all_artists_data})
        return jsonify(success=True, message="Top artists saved successfully!")
    except Exception as e:
        return jsonify(success=False, message=str(e))


@app.route('/create_playlist')
def create_playlist():
    cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_handler=cache_handler)
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        return redirect('/')
    spotify = spotipy.Spotify(auth_manager=auth_manager)

    navigation = generate_navigation(spotify)

    # 1. Identify who is logged in
    user_data = spotify.current_user()
    user_id = user_data['id']

    # 2. Fetch the user's top tracks from Firestore
    user_ref = db.collection('users').document(user_id)
    top_artists_ref = user_ref.collection('user_favorites').document('top_artists')

    top_artists_data = top_artists_ref.get().to_dict()['artists']

    # Filter artists based on the range
    short_term_artists = [artist for artist in top_artists_data if artist['range'] == 'short_term']
    medium_term_artists = [artist for artist in top_artists_data if artist['range'] == 'medium_term']
    long_term_artists = [artist for artist in top_artists_data if artist['range'] == 'long_term']

    # Fetch a larger sample to have a buffer for replacements.
    BUFFER_SIZE = 10
    short_term_sample = sample(short_term_artists, min(BUFFER_SIZE, len(short_term_artists)))
    medium_term_sample = sample(medium_term_artists, min(BUFFER_SIZE, len(medium_term_artists)))
    long_term_sample = sample(long_term_artists, min(BUFFER_SIZE, len(long_term_artists)))

    samples = {
        'short_term': short_term_sample,
        'medium_term': medium_term_sample,
        'long_term': long_term_sample
    }

    seen = set()
    unique_artists = []

    # Helper function to add a unique artist from a term sample.
    def add_unique_artist(term):
        for artist in samples[term]:
            if artist['id'] not in seen:
                seen.add(artist['id'])
                unique_artists.append(artist)
                samples[term].remove(artist)
                return True
        return False

    # Add unique artists until the list contains 5 from each term or the sample lists are exhausted.
    for term in ['short_term', 'medium_term', 'long_term']:
        count = 0
        while count < 5 and samples[term]:
            if add_unique_artist(term):
                count += 1

    # 3. Fetch top 10 tracks for each artist from Spotify
    tracks = []
    for artist in unique_artists:
        artist_tracks = spotify.artist_top_tracks(artist['id'])
        # 4. Randomly select 2 songs from the top tracks
        selected_tracks = sample(artist_tracks['tracks'], 2)
        tracks.extend(selected_tracks)

    random.shuffle(tracks)

    # 5. Render a template that shows all the tracks for user preview
    return navigation + render_template('preview.html', tracks=tracks)


@app.route('/save_playlist', methods=['POST'])
def save_playlist():
    try:
        cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
        auth_manager = spotipy.oauth2.SpotifyOAuth(cache_handler=cache_handler)
        if not auth_manager.validate_token(cache_handler.get_cached_token()):
            return redirect('/')
        spotify = spotipy.Spotify(auth_manager=auth_manager)

        # Extract track_ids from the POST request
        track_ids = request.form['track_ids'].split(',')

        user_data = spotify.current_user()

        # Fetch the user's existing playlists
        user_playlists = spotify.user_playlists(user_data['id'])['items']

        # Check if "Your Missionary Blend" playlist already exists
        playlist_id = None
        for playlist in user_playlists:
            if playlist['name'] == "Your Missionary Blend":
                playlist_id = playlist['id']
                break

        # If playlist exists, overwrite its tracks. Otherwise, create a new playlist.
        if playlist_id:
            # Clear the existing tracks in the playlist
            spotify.playlist_replace_items(playlist_id, [])
            # Add new tracks to the playlist
            spotify.playlist_add_items(playlist_id, track_ids)
        else:
            # Create a new playlist
            playlist = spotify.user_playlist_create(user_data['id'], "Your Missionary Blend")
            # Add tracks to the new playlist
            spotify.playlist_add_items(playlist['id'], track_ids)

        flash("Playlist saved successfully!")
        return jsonify(success=True)
    except Exception as e:
        # Handle the exception and display a helpful message to the user
        flash(str(e))
        return jsonify(success=False, error=str(e))


@app.route('/find_users')
def find_users():
    # Spotify Authentication
    cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_handler=cache_handler)
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        return redirect('/')
    spotify = spotipy.Spotify(auth_manager=auth_manager)

    user_favorites_ref = db.collection_group('user_favorites')
    user_favorites = user_favorites_ref.stream()

    seen_user_ids = set() # Track user IDs that have already been seen
    user_data_list = []

    def divide_by_range(items):
        short_term = [item for item in items if item['range'] == 'short_term']
        medium_term = [item for item in items if item['range'] == 'medium_term']
        long_term = [item for item in items if item['range'] == 'long_term']
        return short_term[:5], medium_term[:5], long_term[:5]

    for user_favorite_doc in user_favorites:
        user_id = user_favorite_doc.reference.parent.parent.id
        if user_id not in seen_user_ids:
            seen_user_ids.add(user_id)

            # Fetch top artists document
            top_artists_ref = db.document(f'users/{user_id}/user_favorites/top_artists')
            top_artists_doc = top_artists_ref.get()
            top_artists_data = top_artists_doc.to_dict() if top_artists_doc.exists else {}
            top_artists = top_artists_data.get('artists', [])  # Assuming 'artists' is a list within the document

            # Fetch top tracks document
            top_tracks_ref = db.document(f'users/{user_id}/user_favorites/top_tracks')
            top_tracks_doc = top_tracks_ref.get()
            top_tracks_data = top_tracks_doc.to_dict() if top_tracks_doc.exists else {}
            top_tracks = top_tracks_data.get('tracks', [])  # Assuming 'tracks' is a list within the document

            short_term_artists, medium_term_artists, long_term_artists = divide_by_range(top_artists)
            short_term_tracks, medium_term_tracks, long_term_tracks = divide_by_range(top_tracks)

            # Append to user data list
            spotify_user_info = spotify.user(user_id)
            display_name = spotify_user_info['display_name']
            user_data = {
                'user_id': user_id,
                'display_name': display_name,
                'artists': {
                    'short_term': short_term_artists,
                    'medium_term': medium_term_artists,
                    'long_term': long_term_artists,
                },
                'tracks': {
                    'short_term': short_term_tracks,
                    'medium_term': medium_term_tracks,
                    'long_term': long_term_tracks,
                }
            }
            user_data_list.append(user_data)

    navigation = generate_navigation(spotify)

    return navigation + render_template("find_users.html", users=user_data_list)



# Helper Functions for Playback Controls in Currently Playing
@app.route('/play_track/<track_uri>', methods=['POST'])
def play_track(track_uri):
    cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(cache_handler=cache_handler)
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        return jsonify(success=False, message="Authentication failed.")

    spotify = spotipy.Spotify(auth_manager=auth_manager)
    try:
        spotify.start_playback(uris=[track_uri])
        return jsonify(success=True)
    except:
        return jsonify(success=False, message="Playback error.")

'''
Following lines allow application to be run more conveniently with
`python app.py` (Make sure you're using python3)
(Also includes directive to leverage pythons threading capacity.)
'''

if __name__ == '__main__':
    # Get the port from the SPOTIPY_REDIRECT_URI environment variable
    redirect_uri = os.environ.get("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8080")
    parsed_uri = urlparse(redirect_uri)
    port = parsed_uri.port if parsed_uri.port is not None else 8080

    app.run(threaded=True, port=int(os.environ.get("PORT", port)))
