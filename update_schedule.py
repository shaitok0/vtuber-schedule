
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

CHANNELS = {
    "緋八マナ": "https://www.youtube.com/@HibachiMana/streams",
    "佐伯イッテツ": "https://www.youtube.com/@Saiki_Supadari/streams",
    "宇佐美リト": "https://www.youtube.com/@usamirito_power/streams",
    "赤城ウェン": "https://www.youtube.com/@akagi_wen/streams",
}

def get_date(video):
    for key in ("release_timestamp", "scheduled_start_time", "timestamp"):
        value = video.get(key)
        if value:
            try:
                return datetime.fromtimestamp(
                    float(value), timezone.utc
                ).isoformat().replace("+00:00", "Z")
            except (ValueError, TypeError, OSError):
                pass

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

    result = subprocess.run(
        [
            "yt-dlp",
            "--dump-single-json",
            "--no-warnings",
            "--ignore-errors",
            "--playlist-end", "50",
            channel_url,
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=True,
    )

    data = json.loads(result.stdout)

    for video in data.get("entries") or []:
        if not video:
            continue

        video_id = video.get("id")
        if not video_id:
            continue

        date_value = get_date(video)
        live_status = video.get("live_status")

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
            print("日時を取得できずスキップ:", name, video_id)
            continue

        if not date_value:
            print("日時を取得できずスキップ:", name, video_id)
            continue

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
            "scheduledAt": date_value,
            "status": status,
        })

    print(name + ": " + str(len(items)) + "件取得")
    return items


def main():
    items = []
    failures = []

    for name, channel_url in CHANNELS.items():
        try:
            items.extend(get_streams(name, channel_url))
        except Exception as error:
            failures.append(name)
            print("取得失敗:", name, str(error))

    unique = {item["videoId"]: item for item in items}
    items = list(unique.values())
    items.sort(key=lambda item: item["scheduledAt"], reverse=True)

    # 一部でも失敗、または0件なら既存データを上書きしない
    if failures:
        raise RuntimeError(
            "取得に失敗したチャンネルがあります。既存データは保存しません: "
            + ", ".join(failures)
        )

    if not items:
        raise RuntimeError(
            "配信データが0件でした。既存データは保存しません。"
        )

    output_path = Path("schedule.json")
    temp_path = Path("schedule.json.tmp")

    with temp_path.open("w", encoding="utf-8") as output:
        json.dump(items, output, ensure_ascii=False, indent=2)

    temp_path.replace(output_path)
    print("Saved", len(items), "streams in total")


if __name__ == "__main__":
    main()
