import base64
from datetime import UTC, datetime
from pathlib import Path

from pai.backup import create_backup

pai_dir = Path(r"C:\Users\Hadi\Documents\ChatGPT\New project\Pai")
env_lines = (pai_dir / ".env").read_text(encoding="utf-8").splitlines()
key = None
for line in env_lines:
    if line.startswith("PAI_BACKUP_KEY="):
        key = line.split("=", 1)[1].strip().strip('"').strip("'")
        break

if not key:
    raise ValueError("Missing PAI_BACKUP_KEY in .env")

raw_key = base64.b64decode(key) if len(key) == 44 else key.encode("utf-8")
timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
dest = pai_dir / "backups" / f"p9-personality-{timestamp}.pai"
create_backup(pai_dir / "pai.sqlite", dest, raw_key[:32])
print(f"Encrypted backup successfully created: {dest}")
