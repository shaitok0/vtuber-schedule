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


def get_recent_videos(channels):
    result = []

    for channel_id, details in channels.items():
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
            batch = ids[start:start + 50]
            videos = api_get("videos", {
                "part": "snippet,liveStreamingDetails",
                "id": ",".join(batch),
            })

            for video in videos.get("items", []):
                snippet = video.get("snippet", {})
                live = video.get("liveStreamingDetails", {})

                if snippet.get("liveBroadcastContent") in ("live", "upcoming"):
                    continue

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

                result.append({
                    "name": details["name"],
                    "title": snippet.get("title", "配信"),
                    "videoId": video["id"],
                    "url": "https://www.youtube.com/watch?v=" + video["id"],
                    "thumbnail": thumbnail,
                    "scheduledAt": iso_time(date_value),
                    "status": "past",
                })

    return result


def search_channel(channel_id, name):
    data = api_get("search", {
        "part": "snippet",
        "channelId": channel_id,
        "type": "video",
        "maxResults": 50,
        "order": "date",
    })

    found = []
    for entry in data.get("items", []):
        video_id = entry.get("id", {}).get("videoId")
        snippet = entry.get("snippet", {})

        if not video_id:
            continue

        status = snippet.get("liveBroadcastContent", "none")
        if status not in ("live", "upcoming"):
            continue

        found.append((video_id, snippet, status))

    # search.list には配信開始予定時刻が含まれないため、
    # videos.list から scheduledStartTime / actualStartTime を取得する
    result = []
    ids = [video_id for video_id, _, _ in found]

    for start in range(0, len(ids), 50):
        batch = ids[start:start + 50]
        details_data = api_get("videos", {
            "part": "snippet,liveStreamingDetails",
            "id": ",".join(batch),
        })
        details_by_id = {
            video["id"]: video for video in details_data.get("items", [])
        }

        for video_id, search_snippet, search_status in found[start:start + 50]:
            video = details_by_id.get(video_id, {})
            snippet = video.get("snippet", search_snippet)
            live = video.get("liveStreamingDetails", {})

            # 予定配信は scheduledStartTime、配信中は actualStartTime を優先
            date_value = (
                live.get("scheduledStartTime")
                or live.get("actualStartTime")
                or snippet.get("publishedAt")
            )

            thumbnails = snippet.get("thumbnails", {})
            thumbnail = (
                thumbnails.get("high")
                or thumbnails.get("medium")
                or thumbnails.get("default")
                or {}
            ).get("url", "")

            result.append({
                "name": name,
                "title": snippet.get("title", "配信"),
                "videoId": video_id,
                "url": "https://www.youtube.com/watch?v=" + video_id,
                "thumbnail": thumbnail,
                "scheduledAt": iso_time(date_value),
                "status": search_status,
            })

    return result


def main():
    if not API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY が見つかりません。")

    now = datetime.now(timezone.utc)

    old_items = []
    if OUTPUT.exists():
        try:
            old_items = json.loads(OUTPUT.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            old_items = []

    channels = get_channels()

    # 最近の配信済み動画
    items = get_recent_videos(channels)

    # 4人を順番に確認。1人あたり約1時間ごと
    channel_list = list(channels.items())
    slot = (now.hour * 4 + now.minute // 15) % 4
    selected_id, selected = channel_list[slot]

    # 今回確認していないメンバーのライブ・予定情報は引き継ぐ
    for item in old_items:
        if item.get("name") != selected["name"]:
            if item.get("status") in ("live", "upcoming"):
                items.append(item)

    # 今回のメンバーの最新状況を取得
    items.extend(search_channel(selected_id, selected["name"]))

    # 重複動画を整理
    unique = {}
    for item in items:
        video_id = item.get("videoId")
        if video_id:
            unique[video_id] = item

    cleaned = list(unique.values())
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

    print(selected["name"] + ": 配信状況を確認しました")
    print("Saved", len(cleaned), "streams in total")


if __name__ == "__main__":
    main()
