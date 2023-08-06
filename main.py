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
from flask import Flask, session, request, redirect, jsonify, render_template
from flask_session import Session
import spotipy
import urllib.parse
from urllib.parse import urlparse
from google.cloud import firestore
from helper_functions import generate_navigation


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
    'playlist-modify-private',
    'user-top-read',
    'app-remote-control',
    'user-modify-playback-state',
    'user-library-modify',
    'user-read-playback-state',
    'user-modify-playback-state'
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
