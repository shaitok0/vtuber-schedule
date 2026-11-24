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
    params = dict(params)
    params["key"] = API_KEY
    url = BASE + "/" + endpoint + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def iso_time(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError):
        return None


def thumbnail_url(snippet):
    thumbs = snippet.get("thumbnails", {})
    return (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")


def get_channels():
    result = {}
    for name, handle in CHANNELS.items():
        data = api_get("channels", {"part": "id,contentDetails", "forHandle": "@" + handle})
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


def get_recent_past(channels):
    result = []
    for details in channels.values():
        data = api_get("playlistItems", {
            "part": "contentDetails",
            "playlistId": details["uploads"],
            "maxResults": 30,
        })
        ids = [
            entry.get("contentDetails", {}).get("videoId")
            for entry in data.get("items", [])
        ]
        ids = [video_id for video_id in ids if video_id]
        for start in range(0, len(ids), 50):
            videos = api_get("videos", {
                "part": "snippet,liveStreamingDetails",
                "id": ",".join(ids[start:start + 50]),
            })
            for video in videos.get("items", []):
                snippet = video.get("snippet", {})
                live = video.get("liveStreamingDetails", {})
                if snippet.get("liveBroadcastContent") in ("live", "upcoming"):
                    continue
                date_value = live.get("actualStartTime") or snippet.get("publishedAt")
                result.append({
                    "name": details["name"],
                    "title": snippet.get("title", "配信"),
                    "videoId": video["id"],
                    "url": "https://www.youtube.com/watch?v=" + video["id"],
                    "thumbnail": thumbnail_url(snippet),
                    "scheduledAt": iso_time(date_value),
                    "status": "past",
                })
    return result


def get_current_streams(channel_id, name):
    found = {}
    # eventType=live / upcoming を別々に検索し、4人全員を毎回確認する
    for event_type, status in (("live", "live"), ("upcoming", "upcoming")):
        data = api_get("search", {
            "part": "snippet",
            "channelId": channel_id,
            "type": "video",
            "eventType": event_type,
            "maxResults": 50,
            "order": "date",
        })
        for entry in data.get("items", []):
            video_id = entry.get("id", {}).get("videoId")
            if video_id:
                found[video_id] = status

    result = []
    ids = list(found)
    for start in range(0, len(ids), 50):
        details_data = api_get("videos", {
            "part": "snippet,liveStreamingDetails",
            "id": ",".join(ids[start:start + 50]),
        })
        for video in details_data.get("items", []):
            snippet = video.get("snippet", {})
            live = video.get("liveStreamingDetails", {})
            status = found[video["id"]]
            date_value = (
                live.get("scheduledStartTime") if status == "upcoming"
                else live.get("actualStartTime")
            ) or snippet.get("publishedAt")
            result.append({
                "name": name,
                "title": snippet.get("title", "配信"),
                "videoId": video["id"],
                "url": "https://www.youtube.com/watch?v=" + video["id"],
                "thumbnail": thumbnail_url(snippet),
                "scheduledAt": iso_time(date_value),
                "status": status,
            })
    return result


def main():
    if not API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY が見つかりません。")

    old_items = []
    if OUTPUT.exists():
        try:
            loaded = json.loads(OUTPUT.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                old_items = loaded
        except (json.JSONDecodeError, OSError):
            raise RuntimeError("既存のschedule.jsonを読み込めません。安全のため更新を中止します。")

    channels = get_channels()
    recent_past = get_recent_past(channels)

    # 4人全員の配信中・配信予定を毎回確認
    current_active = []
    for channel_id, details in channels.items():
        current_active.extend(get_current_streams(channel_id, details["name"]))
        print(details["name"] + ": 配信状況を確認しました")

    active_ids = {item["videoId"] for item in current_active}
    preserved = []
    for item in old_items:
        if not isinstance(item, dict) or not item.get("videoId"):
            continue
        if item.get("status") == "past":
            preserved.append(item)
        elif item.get("status") in ("live", "upcoming") and item["videoId"] not in active_ids:
            ended = dict(item)
            ended["status"] = "past"
            preserved.append(ended)

    unique = {}
    for item in preserved + recent_past + current_active:
        video_id = item.get("videoId")
        if video_id:
            unique[video_id] = item

    cleaned = list(unique.values())
    cleaned.sort(key=lambda item: item.get("scheduledAt") or "", reverse=True)

    temp = OUTPUT.with_suffix(".json.tmp")
    temp.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(OUTPUT)

    print("4人全員の確認が完了しました")
    print("Saved", len(cleaned), "streams in total")


if __name__ == "__main__":
    main()
