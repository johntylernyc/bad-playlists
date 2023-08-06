def generate_navigation(spotify):
    navigation = f'''
        <h2>Hi {spotify.me()["display_name"]}, 
            <small><a href="/sign_out">[sign out]</a></small>
        </h2>
        <a href="/playlists">my playlists</a> | 
        <a href="/currently_playing">currently playing</a> | 
        <a href="/current_user">me</a> | 
        <a href="/top_tracks">top tracks</a> | 
        <a href="/top_artists">top artists</a>
        <hr>
        <br>
    '''
    return navigation