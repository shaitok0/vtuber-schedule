
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

CHANNELS = {
    "緋八マナ": "hibachimana",
    "佐伯イッテツ": "saikiittetsu",
    "宇佐美リト": "usamirito",
    "赤城ウェン": "akagiwen",
}

BASE = "https://www.googleapis.com/youtube/v3"
OUTPUT = Path("schedule.json")


def api_get(endpoint, params):
    params["key"] = API_KEY
    url = BASE + "/" + endpoint + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url, headers={"Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except (ValueError, TypeError):
        return None


def iso_time(value):
    if not value:
        return None
    parsed = parse_time(value)
    return parsed.astimezone(timezone.utc).isoformat().replace(
        "+00:00", "Z"
    ) if parsed else None


def get_channels():
    result = {}
    for name, handle in CHANNELS.items():
        data = api_get("channels", {
            "part": "id,contentDetails",
            "forHandle": "@" + handle,
        })
        entries = data.get("items", [])
        if not entries:
            raise RuntimeError("チャンネルが見つかりません: " + name)
        channel = entries[0]
        result[channel["id"]] = {
            "name": name,
            "uploads": channel["contentDetails"]["relatedPlaylists"]["uploads"],
        }
        print(name + ": チャンネル確認OK")
    return result


def get_video_details(video_ids, names_by_channel):
    items = []
    for start in range(0, len(video_ids), 50):
        batch = video_ids[start:start + 50]
        if not batch:
            continue

        data = api_get("videos", {
            "part": "snippet,liveStreamingDetails",
            "id": ",".join(batch),
        })

        for video in data.get("items", []):
            snippet = video.get("snippet", {})
            channel_id = snippet.get("channelId")
            name = names_by_channel.get(channel_id)
            if not name:
                continue

            live = video.get("liveStreamingDetails", {})
            broadcast = snippet.get("liveBroadcastContent", "none")

            if broadcast == "live":
                status = "live"
                date_value = (
                    live.get("actualStartTime")
                    or snippet.get("publishedAt")
                )
            elif broadcast == "upcoming":
                status = "upcoming"
                date_value = (
                    live.get("scheduledStartTime")
                    or snippet.get("publishedAt")
                )
            else:
                status = "past"
                date_value = (
                    live.get("actualStartTime")
                    or snippet.get("publishedAt")
                )

            thumbnails = snippet.get("thumbnails", {})
            thumbnail = (
                thumbnails.get("high")
                or thumbnails.get("medium")
                or thumbnails.get("default")
                or {}
            ).get("url", "")

            items.append({
                "name": name,
                "title": snippet.get("title", "配信"),
                "videoId": video["id"],
                "url": "https://www.youtube.com/watch?v=" + video["id"],
                "thumbnail": thumbnail,
                "scheduledAt": iso_time(date_value),
                "status": status,
            })

    return items


def get_upcoming(channel_id, name):
    data = api_get("search", {
        "part": "snippet",
        "channelId": channel_id,
        "type": "video",
        "eventType": "upcoming",
        "maxResults": 10,
        "order": "date",
    })

    result = []
    for entry in data.get("items", []):
        video_id = entry.get("id", {}).get("videoId")
        if video_id:
            result.append({
                "name": name,
                "title": entry.get("snippet", {}).get("title", "配信予定"),
                "videoId": video_id,
                "url": "https://www.youtube.com/watch?v=" + video_id,
                "thumbnail": (
                    entry.get("snippet", {})
                    .get("thumbnails", {})
                    .get("high", {})
                    .get("url", "")
                ),
                "scheduledAt": None,
                "status": "upcoming",
            })
    return result


def main():
    if not API_KEY:
        raise RuntimeError(
            "YOUTUBE_API_KEY が見つかりません。GitHub Secretsとworkflowを確認してください。"
        )

    now = datetime.now(timezone.utc)
    old_items = []
    if OUTPUT.exists():
        try:
            old_items = json.loads(OUTPUT.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            old_items = []

    channels = get_channels()
    names_by_channel = {
        channel_id: details["name"]
        for channel_id, details in channels.items()
    }

    video_ids = []
    for details in channels.values():
        data = api_get("playlistItems", {
            "part": "contentDetails",
            "playlistId": details["uploads"],
            "maxResults": 50,
        })
        for entry in data.get("items", []):
            video_id = entry.get("contentDetails", {}).get("videoId")
            if video_id:
                video_ids.append(video_id)

    fresh = get_video_details(
        list(dict.fromkeys(video_ids)), names_by_channel
    )

    # 予定配信検索は6時間ごとに実行し、API利用枠を節約する
    if now.hour % 6 == 0 and now.minute < 5:
        for channel_id, details in channels.items():
            try:
                fresh.extend(get_upcoming(channel_id, details["name"]))
                print(details["name"] + ": 予定検索OK")
            except Exception as error:
                print(
                    details["name"] + ": 予定検索失敗:", str(error)
                )

    # 新しい結果を優先し、検索していない予定情報も保持する
    merged = {item["videoId"]: item for item in old_items if item.get("videoId")}
    for item in fresh:
        merged[item["videoId"]] = item

    # 期限切れの予定は、最新情報で確認できなければ一覧から除く
    cleaned = []
    for item in merged.values():
        scheduled = parse_time(item.get("scheduledAt"))
        if item.get("status") == "upcoming" and scheduled and scheduled < now:
            continue
        cleaned.append(item)

    # 日時のある項目を新しい順にし、日時不明は後ろにする
    cleaned.sort(
        key=lambda item: item.get("scheduledAt") or "",
        reverse=True,
    )

    temp = OUTPUT.with_suffix(".json.tmp")
    temp.write_text(
        json.dumps(cleaned, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp.replace(OUTPUT)
    print("Saved", len(cleaned), "streams in total")


if __name__ == "__main__":
    main()
