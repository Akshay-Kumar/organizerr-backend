from app.models import Torrent


def build_display_name(torrent: Torrent) -> str:
    base = (
        torrent.correct_name
        or torrent.name
        or "Unknown"
    )

    media_type = (torrent.media_type or "").lower()

    # Individual episode
    if media_type == "episode":
        if torrent.season is not None and torrent.episode is not None:
            return f"{base} - S{torrent.season:02d}E{torrent.episode:02d}"

        if torrent.episode is not None:
            return f"{base} - EP {torrent.episode:02d}"

    # TV season/show
    if media_type == "tv":
        if torrent.season is not None:
            return f"{base} - Season {torrent.season}"

    return base