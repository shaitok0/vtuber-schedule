
import json
import subprocess
from datetime import datetime, timezone

CHANNELS = {
    "緋八マナ": "https://www.youtube.com/@HibachiMana/streams",
    "佐伯イッテツ": "https://www.youtube.com/@SaikiIttetsu/streams",
    "宇佐美リト": "https://www.youtube.com/@UsamiRito/streams",
    "赤城ウェン": "https://www.youtube.com/@AkagiWen/streams",
}

def get_streams(name, channel_url):
    items = []

    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--flat-playlist",
                "--dump-single-json",
                "--no-warnings",
                "--ignore-errors",
                "--playlist-end", "50",
                channel_url,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )

        data = json.loads(result.stdout)

        for video in data.get("entries") or []:
            if not video:
                continue

            video_id = video.get("id")
            if not video_id:
                continue

            live_status = video.get("live_status")
            scheduled = (
                video.get("release_timestamp")
                or video.get("timestamp")
            )

            if live_status == "is_live":
                status = "live"
            elif live_status == "is_upcoming":
                status = "upcoming"
            elif live_status in ("was_live", "not_live"):
                status = "past"
            elif scheduled:
                status = (
                    "upcoming"
                    if scheduled > datetime.now(timezone.utc).timestamp()
                    else "past"
                )
            else:
                continue

            if scheduled:
                scheduled_at = datetime.fromtimestamp(
                    scheduled, timezone.utc
                ).isoformat().replace("+00:00", "Z")
            else:
                scheduled_at = datetime.now(timezone.utc).isoformat()

            thumbnails = video.get("thumbnails") or []
            thumbnail = (
                video.get("thumbnail")
                or (thumbnails[-1].get("url") if thumbnails else "")
            )

            items.append({
                "name": name,
                "title": video.get("title") or "配信",
                "videoId": video_id,
                "url": "https://www.youtube.com/watch?v=" + video_id,
                "thumbnail": thumbnail,
                "scheduledAt": scheduled_at,
                "status": status,
            })

        print(
            name + ": "
            + str(sum(x["status"] == "live" for x in items))
            + " live, "
            + str(sum(x["status"] == "upcoming" for x in items))
            + " upcoming, "
            + str(sum(x["status"] == "past" for x in items))
            + " past"
        )

    except Exception as error:
        print("Error for " + name + ": " + str(error))

    return items


items = []
for name, channel_url in CHANNELS.items():
    items.extend(get_streams(name, channel_url))

items.sort(key=lambda item: item["scheduledAt"], reverse=True)

with open("schedule.json", "w", encoding="utf-8") as output:
    json.dump(items, output, ensure_ascii=False, indent=2)

print("Saved", len(items), "streams in total")
