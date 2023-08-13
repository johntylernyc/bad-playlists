# current.py

from flask import Blueprint, render_template, redirect
import spotipy
from .authentication import ensure_authenticated

current = Blueprint('current', __name__)


@current.route('/playlists')
def playlists():
    auth_manager = ensure_authenticated()
    if not auth_manager:
        return redirect('/auth/login_with_spotify')

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

    return render_template('playlists.html', playlists=formatted_playlists)


@current.route('/currently_playing')
def currently_playing():
    auth_manager = ensure_authenticated()
    if not auth_manager:
        return redirect('/auth/login_with_spotify')

    spotify = spotipy.Spotify(auth_manager=auth_manager)

    track = spotify.current_user_playing_track()

    if track:
        artist_id = track['item']['artists'][0]['id']
        top_tracks = spotify.artist_top_tracks(artist_id, country='US')['tracks']
        context = {
            'album_art_url': track['item']['album']['images'][0]['url'],
            'track_name': track['item']['name'],
            'artist_name': track['item']['artists'][0]['name'],
            'top_tracks': top_tracks
        }
    else:
        context = {
            'album_art_url': None,
            'track_name': None,
            'artist_name': None,
            'top_tracks': None
        }

    return render_template("currently_playing.html", context=context)


@current.route('/current_user')
def current_user():
    auth_manager = ensure_authenticated()
    if not auth_manager:
        return redirect('/auth/login_with_spotify')

    spotify = spotipy.Spotify(auth_manager=auth_manager)

    user_data = spotify.current_user()

    # Extract relevant data fields
    display_name = user_data.get("display_name")
    followers_count = user_data.get("followers", {}).get("total")
    external_url = user_data.get("external_urls", {}).get("spotify")
    country = user_data.get("country")
    email = user_data.get("email")
    product = user_data.get("product")

    return render_template(
        'current_user.html',
        display_name=display_name,
        followers_count=followers_count,
        external_url=external_url,
        country=country,
        email=email,
        product=product
    )