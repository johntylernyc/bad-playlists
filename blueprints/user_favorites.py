from flask import Blueprint, request, session, redirect, render_template, jsonify
import spotipy
from .authentication import ensure_authenticated
from google.cloud import firestore

user_favorites = Blueprint('user_favorites', __name__)
db = firestore.Client()


@user_favorites.route('/top_tracks')
def top_tracks():
    auth_manager = ensure_authenticated()
    if not auth_manager:
        return redirect('/auth/login_with_spotify')  # Modify this redirect to your desired route

    spotify = spotipy.Spotify(auth_manager=auth_manager)
    ranges = ['short_term', 'medium_term', 'long_term']

    tracks = {}

    for sp_range in ranges:
        tracks[sp_range] = spotify.current_user_top_tracks(time_range=sp_range, limit=50)['items']

    return render_template("top_tracks.html", tracks=tracks)


@user_favorites.route('/save_top_tracks', methods=['POST'])
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


@user_favorites.route('/top_artists')
def top_artists():
    auth_manager = ensure_authenticated()
    if not auth_manager:
        return redirect('/auth/login_with_spotify')  # Modify this redirect to your desired route

    spotify = spotipy.Spotify(auth_manager=auth_manager)
    ranges = ['short_term', 'medium_term', 'long_term']

    artists = {}

    for sp_range in ranges:
        artists[sp_range] = spotify.current_user_top_artists(time_range=sp_range, limit=50)['items']

    return render_template("top_artists.html", artists=artists)


@user_favorites.route('/save_top_artists', methods=['POST'])
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