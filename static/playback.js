function playTrack(trackURI) {
    $.post("/play_track/" + trackURI, function(data) {
        if (!data.success) {
            alert("Error: " + data.message);
        }
    });
}