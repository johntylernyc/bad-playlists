import spotipy
import os
from flask import Blueprint, request, session, redirect
SPOTIPY_REDIRECT_URI = os.environ.get('SPOTIPY_REDIRECT_URI')

authentication = Blueprint('authentication', __name__)

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

@authentication.route('/callback')
def callback():
    print(f"Using Redirect URI: {SPOTIPY_REDIRECT_URI}")

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


@authentication.route('/login_with_spotify')
def login_with_spotify():
    print(f"Using Redirect URI: {SPOTIPY_REDIRECT_URI}")

    cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(scope=scope,
                                               cache_handler=cache_handler,
                                               redirect_uri=SPOTIPY_REDIRECT_URI,
                                               show_dialog=False)
    auth_url = auth_manager.get_authorize_url()
    return redirect(auth_url)


@authentication.route('/sign_out')
def sign_out():
    session.pop("token_info", None)
    session.clear()
    return redirect('/')


def ensure_authenticated():
    cache_handler = spotipy.cache_handler.FlaskSessionCacheHandler(session)
    auth_manager = spotipy.oauth2.SpotifyOAuth(scope=scope,
                                               cache_handler=cache_handler,
                                               redirect_uri=SPOTIPY_REDIRECT_URI,
                                               show_dialog=True)
    if not auth_manager.validate_token(cache_handler.get_cached_token()):
        return None
    session['token_info'] = auth_manager.get_cached_token()  # Store token info in session
    return auth_manager
