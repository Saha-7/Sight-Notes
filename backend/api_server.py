"""
SightNotes API Server
Serves notes from the notes/ folder to the React frontend.
Run alongside main.py: python api_server.py
"""

from flask import Flask, jsonify
from flask_cors import CORS
import os
import glob

app = Flask(__name__)
CORS(app)

NOTES_DIR = os.path.join(os.path.dirname(__file__), "notes")


@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    """List all note session files."""
    if not os.path.exists(NOTES_DIR):
        return jsonify([])
    files = sorted(glob.glob(os.path.join(NOTES_DIR, "*.md")), reverse=True)
    sessions = []
    for f in files:
        name = os.path.basename(f)
        size = os.path.getsize(f)
        mtime = os.path.getmtime(f)
        sessions.append({
            "filename": name,
            "path": f,
            "size": size,
            "modified": mtime
        })
    return jsonify(sessions)


@app.route("/api/notes/<filename>", methods=["GET"])
def get_notes(filename):
    """Get content of a specific notes file."""
    filepath = os.path.join(NOTES_DIR, filename)
    if not os.path.exists(filepath) or not filename.endswith(".md"):
        return jsonify({"error": "Not found"}), 404
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    # Parse snapshots
    snapshots = parse_snapshots(content)
    return jsonify({
        "filename": filename,
        "content": content,
        "snapshots": snapshots,
        "count": len(snapshots)
    })


@app.route("/api/latest", methods=["GET"])
def get_latest():
    """Get the most recently modified notes file."""
    if not os.path.exists(NOTES_DIR):
        return jsonify({"error": "No notes yet"}), 404
    files = sorted(glob.glob(os.path.join(NOTES_DIR, "*.md")),
                   key=os.path.getmtime, reverse=True)
    if not files:
        return jsonify({"error": "No notes yet"}), 404
    filename = os.path.basename(files[0])
    with open(files[0], "r", encoding="utf-8") as f:
        content = f.read()
    snapshots = parse_snapshots(content)
    return jsonify({
        "filename": filename,
        "content": content,
        "snapshots": snapshots,
        "count": len(snapshots)
    })


def parse_snapshots(content: str) -> list:
    """Split markdown content into individual snapshots."""
    parts = content.split("## Snapshot ")
    snapshots = []
    for part in parts[1:]:  # skip header
        lines = part.strip().split("\n")
        num = lines[0].strip()
        body = "\n".join(lines[1:]).strip().lstrip("---").strip()
        snapshots.append({"number": num, "content": body})
    return snapshots


if __name__ == "__main__":
    print("🚀 SightNotes API running at http://localhost:5001")
    app.run(port=5001, debug=False)