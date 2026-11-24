
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


def refresh_old_live_items(old_items):
    """以前の配信中・配信予定を videos.list で確認し、終了済みなら過去にする。"""
    old_active = [
        item for item in old_items
        if item.get("status") in ("live", "upcoming") and item.get("videoId")
    ]

    if not old_active:
        return []

    result = []
    ids = list(dict.fromkeys(item["videoId"] for item in old_active))
    video_data = {}

    for start in range(0, len(ids), 50):
        batch = ids[start:start + 50]
        data = api_get("videos", {
            "part": "snippet,liveStreamingDetails",
            "id": ",".join(batch),
        })
        for video in data.get("items", []):
            video_data[video["id"]] = video

    for old in old_active:
        item = dict(old)
        video = video_data.get(item["videoId"])

        # APIから動画が見つからない場合も、古い配信中表示を残さない
        if video is None:
            item["status"] = "past"
            result.append(item)
            continue

        snippet = video.get("snippet", {})
        live = video.get("liveStreamingDetails", {})
        current_status = snippet.get("liveBroadcastContent", "none")

        item["title"] = snippet.get("title") or item.get("title", "配信")
        thumbnails = snippet.get("thumbnails", {})
        thumbnail = (
            thumbnails.get("high")
            or thumbnails.get("medium")
            or thumbnails.get("default")
            or {}
        ).get("url")
        if thumbnail:
            item["thumbnail"] = thumbnail

        if current_status in ("live", "upcoming"):
            item["status"] = current_status
            date_value = (
                live.get("scheduledStartTime")
                or live.get("actualStartTime")
                or item.get("scheduledAt")
            )
        else:
            item["status"] = "past"
            date_value = (
                live.get("actualStartTime")
                or snippet.get("publishedAt")
                or item.get("scheduledAt")
            )

        item["scheduledAt"] = iso_time(date_value) or item.get("scheduledAt")
        result.append(item)

    return result


def search_channel(channel_id, name):
    data = api_get("search", {
        "part": "snippet",
        "channelId": channel_id,
        "type": "video",
        "maxResults": 50,
        "order": "date",
    })

    result = []

    for entry in data.get("items", []):
        video_id = entry.get("id", {}).get("videoId")
        snippet = entry.get("snippet", {})

        if not video_id:
            continue

        status = snippet.get("liveBroadcastContent", "none")
        if status not in ("live", "upcoming"):
            continue

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
            "scheduledAt": None,
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
            else:
                raise RuntimeError("schedule.json の形式がリストではありません。")
        except (json.JSONDecodeError, OSError) as error:
            raise RuntimeError("既存の schedule.json を読み込めないため、上書きを中止します。") from error

    channels = get_channels()

    # 既存の過去配信はすべて引き継ぐ（直近30件より古い履歴も残す）
    old_past_items = [
        item for item in old_items
        if item.get("status") == "past" and item.get("videoId")
    ]

    # 既存の配信中・予定を全件確認し、終了済みなら「過去」に変更
    refreshed_old_active = refresh_old_live_items(old_items)

    # 各メンバーの直近動画も取得
    recent_items = get_recent_videos(channels)

    # 4人を順番に確認。1人あたり約1時間ごと
    channel_list = list(channels.items())
    now = datetime.now(timezone.utc)
    slot = (now.hour * 4 + now.minute // 15) % 4
    selected_id, selected = channel_list[slot]

    # 今回のメンバーの最新状況を取得
    selected_live_items = search_channel(selected_id, selected["name"])

    # 同じ動画IDは新しい情報を優先してまとめる
    unique = {}
    for item in old_past_items:
        unique[item["videoId"]] = item
    for item in refreshed_old_active:
        unique[item["videoId"]] = item
    for item in recent_items:
        unique[item["videoId"]] = item
    for item in selected_live_items:
        unique[item["videoId"]] = item

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
