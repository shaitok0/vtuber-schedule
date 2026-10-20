
import json
import subprocess
from datetime import datetime, timezone

CHANNELS = {
    "緋八マナ": "https://www.youtube.com/@HibachiMana/streams",
    "佐伯イッテツ": "https://www.youtube.com/@Saiki_Supadari/streams",
    "宇佐美リト": "https://www.youtube.com/@usamirito_power/streams",
    "赤城ウェン": "https://www.youtube.com/@akagi_wen/streams",
}

def get_date(video):
    # 配信予定日時・配信日時を優先
    for key in ("release_timestamp", "scheduled_start_time", "timestamp"):
        value = video.get(key)
        if value:
            try:
                return datetime.fromtimestamp(
                    float(value), timezone.utc
                ).isoformat().replace("+00:00", "Z")
            except (ValueError, TypeError, OSError):
                pass

    # 日時がない過去動画は、YouTubeの投稿日を使用
    upload_date = video.get("upload_date")
    if upload_date:
        try:
            date = datetime.strptime(upload_date, "%Y%m%d")
            return date.replace(
                tzinfo=timezone.utc
            ).isoformat().replace("+00:00", "Z")
        except ValueError:
            pass

    return None


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
            timeout=180,
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
            date_value = get_date(video)

            if live_status == "is_live":
                status = "live"
            elif live_status == "is_upcoming":
                status = "upcoming"
            elif live_status in ("was_live", "not_live"):
                status = "past"
            elif date_value:
                date = datetime.fromisoformat(
                    date_value.replace("Z", "+00:00")
                )
                status = (
                    "upcoming"
                    if date > datetime.now(timezone.utc)
                    else "past"
                )
            else:
                # 日時が取得できない動画を誤った日時で表示しない
                print("日時不明:", name, video_id)
                continue

            if not date_value:
                print("日時不明:", name, video_id)
                continue

            thumbnails = video.get("thumbnails") or []
            thumbnail = (
                video.get("thumbnail")
                or (
                    thumbnails[-1].get("url")
                    if thumbnails else ""
                )
            )

            items.append({
                "name": name,
                "title": video.get("title") or "配信",
                "videoId": video_id,
                "url": "https://www.youtube.com/watch?v=" + video_id,
                "thumbnail": thumbnail,
                "scheduledAt": date_value,
                "status": status,
            })

        print(name + ": " + str(len(items)) + "件取得")

    except Exception as error:
        print("Error for " + name + ": " + str(error))

    return items


items = []
for name, channel_url in CHANNELS.items():
    items.extend(get_streams(name, channel_url))

# 同じ動画を重複させない
unique = {item["videoId"]: item for item in items}
items = list(unique.values())

# 日時の新しい順
items.sort(key=lambda item: item["scheduledAt"], reverse=True)

with open("schedule.json", "w", encoding="utf-8") as output:
    json.dump(items, output, ensure_ascii=False, indent=2)

print("Saved", len(items), "streams in total")
