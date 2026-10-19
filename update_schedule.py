import json
import os
import urllib.parse
import urllib.request

API_KEY = os.environ["YOUTUBE_API_KEY"]
CHANNELS = {
    "緋八マナ": "HibachiMana",
    "佐伯イッテツ": "SaikiIttetsu",
    "宇佐美リト": "UsamiRito",
    "赤城ウェン": "AkagiWen",
}

def api_get(endpoint, params):
    params["key"] = API_KEY
    url = "https://www.googleapis.com/youtube/v3/" + endpoint + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)

items = []
for name, handle in CHANNELS.items():
    try:
        channel_data = api_get("channels", {"part": "id,snippet", "forHandle": handle})
        channels = channel_data.get("items", [])
        if not channels:
            print("Channel not found:", name, handle)
            continue
        channel_id = channels[0]["id"]
        result = api_get("search", {
            "part": "snippet",
            "channelId": channel_id,
            "type": "video",
            "eventType": "upcoming",
            "maxResults": 10,
            "order": "date",
        })
        for video in result.get("items", []):
            snippet = video["snippet"]
            items.append({
                "name": name,
                "title": snippet.get("title", "配信予定"),
                "videoId": video["id"]["videoId"],
                "url": "https://www.youtube.com/watch?v=" + video["id"]["videoId"],
                "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                "scheduledAt": snippet.get("publishedAt", ""),
            })
    except Exception as error:
        print("Error for", name, ":", error)

items.sort(key=lambda item: item["scheduledAt"])
with open("schedule.json", "w", encoding="utf-8") as output:
    json.dump(items, output, ensure_ascii=False, indent=2)
print("Saved", len(items), "upcoming streams")
