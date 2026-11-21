import json
import urllib.request
from pathlib import Path


def get_token():
    env_path = Path("Pai/.env")
    if not env_path.exists():
        env_path = Path(".env")
    with open(env_path) as f:
        for line in f:
            if line.startswith("DISCORD_TOKEN="):
                return line.strip().split("=", 1)[1]
    return ""


token = get_token()
headers = {"Authorization": f"Bot {token}", "User-Agent": "DiscordBot (Pai, 1.0)"}

channels = [
    (1036614013527801876, "study"),
    (1220389554289250526, "moments"),
]

for ch_id, ch_name in channels:
    url = f"https://discord.com/api/v10/channels/{ch_id}/messages?limit=3"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            print(f"=== Channel #{ch_name} ({ch_id}) ===")
            for msg in reversed(data):
                author = msg["author"]["username"]
                content = msg.get("content", "")
                print(f"[{author}]: {content}")
    except Exception as e:
        print(f"Error fetching #{ch_name}: {e}")

# Also check permissions in #study
req_ch = urllib.request.Request(
    "https://discord.com/api/v10/channels/1036614013527801876", headers=headers
)
try:
    with urllib.request.urlopen(req_ch) as resp:
        ch_info = json.loads(resp.read().decode())
        print("\n#study overwrites:", ch_info.get("permission_overwrites", []))
except Exception as e:
    print("Error fetching channel info:", e)
