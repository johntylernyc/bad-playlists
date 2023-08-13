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
from flask import Flask, session, request, redirect, jsonify, render_template, flash, url_for
from flask_session import Session
import spotipy
import urllib.parse
from urllib.parse import urlparse
from google.cloud import firestore
from helper_functions import generate_navigation
from random import sample
import random

from blueprints.authentication import authentication, ensure_authenticated
from blueprints.user_favorites import user_favorites
from blueprints.current import current

app = Flask(__name__, template_folder='templates')
app.register_blueprint(authentication, url_prefix='/auth')
app.register_blueprint(user_favorites)
app.register_blueprint(current)

SPOTIPY_CLIENT_ID = os.environ.get('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.environ.get('SPOTIPY_CLIENT_SECRET')
SPOTIPY_REDIRECT_URI = os.environ.get('SPOTIPY_REDIRECT_URI')
FLASK_SECRET_KEY = os.environ.get('FLASK_SECRET_KEY')
encoded_redirect_uri = urllib.parse.quote(SPOTIPY_REDIRECT_URI)

app.config['SESSION_TYPE'] = 'cookie'  # Use cookie-based sessions
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = '/tmp'

Session(app)

db = firestore.Client()


@app.context_processor
def inject_navigation():
    auth_manager = ensure_authenticated()
    if not auth_manager:
        # If not authenticated, don't attempt to generate navigation
        return dict(navigation=None)

    spotify = spotipy.Spotify(auth_manager=auth_manager)
    navigation = generate_navigation(spotify)
    return dict(navigation=navigation)


@app.route('/')
def index():
    auth_manager = ensure_authenticated()
    if not auth_manager:
        return '<a href="/auth/login_with_spotify">Login with Spotify</a>'

    return render_template("current_user.html", auth_manager=auth_manager)


@app.route('/create_playlist')
def create_playlist():
    auth_manager = ensure_authenticated()
    if not auth_manager:
        return redirect('/auth/login_with_spotify')

    spotify = spotipy.Spotify(auth_manager=auth_manager)

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
    return render_template('preview.html', tracks=tracks)


@app.route('/save_playlist', methods=['POST'])
def save_playlist():
    try:
        auth_manager = ensure_authenticated()
        if not auth_manager:
            return redirect('/auth/login_with_spotify')

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
    auth_manager = ensure_authenticated()
    if not auth_manager:
        return redirect('/auth/login_with_spotify')

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

    return render_template("find_users.html", users=user_data_list)


# Helper Functions for Playback Controls in Currently Playing
@app.route('/play_track/<track_uri>', methods=['POST'])
def play_track(track_uri):
    auth_manager = ensure_authenticated()
    if not auth_manager:
        return redirect('/auth/login_with_spotify')

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
    redirect_uri = os.environ.get("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:5000")
    parsed_uri = urlparse(redirect_uri)
    port = parsed_uri.port if parsed_uri.port is not None else 8080

    app.run(threaded=True, port=int(os.environ.get("PORT", port)))
