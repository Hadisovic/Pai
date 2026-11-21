import os
import zipfile

files_to_pack = ["main.py", "requirements.txt", ".pai-policy.json.example"]
dirs_to_pack = ["src"]

zip_path = "deploy.zip"
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
    for f in files_to_pack:
        if os.path.exists(f):
            zipf.write(f, arcname=f)
            print(f"Added file: {f}")
    for d in dirs_to_pack:
        for root, dirs, files in os.walk(d):
            if "__pycache__" in root:
                continue
            for file in files:
                if file.endswith(".pyc"):
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, ".")
                zipf.write(full_path, arcname=rel_path)
                print(f"Added {rel_path}")

size_kb = os.path.getsize(zip_path) / 1024
print(f"Created deploy.zip ({size_kb:.1f} KB)")
