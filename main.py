import os
import json
import paramiko
import shutil
import subprocess
import re
from flask import Flask, render_template, jsonify, abort, Response
from threading import Thread
from scp import SCPClient
from concurrent.futures import ThreadPoolExecutor

# Load config
with open("config.json", "r") as config_file:
    config = json.load(config_file)

local_recordings_folder = config["steam_recordings_folder"]
ssh_config = config.get("ssh", {})

ssh_enabled = ssh_config.get("enabled", False)
remote_recordings_folder = ssh_config.get("remote_path")
stream_cache_folder = os.path.join(os.getcwd(), "stream-cache")

syncing = False

app = Flask(__name__)

# Function to sync SSH folder into /stream-cache/
def sync_ssh_to_cache():
    global syncing
    if not ssh_enabled:
        print("SSH sync is not enabled.")
        return
    if syncing:
        print("Sync already in progress.")
        return
    syncing = True
    print("Starting SCP sync...")

    try:
        # Clear and recreate cache
        if os.path.exists(stream_cache_folder):
            shutil.rmtree(stream_cache_folder)
        os.makedirs(stream_cache_folder, exist_ok=True)

        # Establish SSH connection
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=ssh_config["host"],
            port=ssh_config["port"],
            username=ssh_config["username"],
            password=ssh_config["password"],
            timeout=60,  # Increase timeout
            compress=True
        )

        # Use SCP for transfer
        with SCPClient(ssh.get_transport()) as scp:
            print(f"Syncing contents of {remote_recordings_folder} to {stream_cache_folder}...")
            # Use the wildcard to only copy the contents
            scp.get(f"{remote_recordings_folder}clips/", stream_cache_folder, recursive=True)
            scp.get(f"{remote_recordings_folder}video/", stream_cache_folder, recursive=True)
            print("SCP sync completed successfully.")

    except Exception as e:
        print(f"Error during SCP sync: {e}")
    finally:
        syncing = False


@app.route("/")
def home():
    return render_template("index.html")

@app.route("/videos")
def list_videos():
    while syncing:
        pass  # Wait for syncing to complete
    videos = []
    video_cache_folder = os.path.abspath("video-cache")
    os.makedirs(video_cache_folder, exist_ok=True)

    recordings_folder = os.path.abspath("stream-cache")  # Absolute path to your recordings folder

    for root, dirs, files in os.walk(recordings_folder):
        for file in files:
            if file == "session.mpd":
                dash_file_path = os.path.join(root, file)
                relative_path = os.path.relpath(root, recordings_folder)
                sanitized_path = relative_path.replace(os.sep, "_").replace(" ", "_")
                output_file_name = f"{sanitized_path}.mp4"
                output_file_path = os.path.join(video_cache_folder, output_file_name)

                print(f"Processing MPD: {dash_file_path}")
                print(f"Output MP4 Path: {output_file_path}")

                try:
                    # Replace start="PT*S" with start="PT0.0S" in the MPD file
                    with open(dash_file_path, "r+") as mpd_file:
                        mpd_content = mpd_file.read()
                        updated_content = re.sub(
                            r'<Period id="0" start="PT[^"]+">',
                            '<Period id="0" start="PT0.0S">',
                            mpd_content
                        )
                        mpd_file.seek(0)
                        mpd_file.write(updated_content)
                        mpd_file.truncate()

                    # Remux using FFmpeg with absolute path
                    absolute_dash_file_path = os.path.abspath(dash_file_path)
                    ffmpeg_command = [
                        "ffmpeg",
                        "-y",  # Add the -y flag to always overwrite
                        "-i", absolute_dash_file_path,
                        "-c", "copy",
                        output_file_path,
                    ]

                    print(f"Executing FFmpeg: {' '.join(ffmpeg_command)}")
                    subprocess.run(ffmpeg_command, check=True)
                    print(f"Successfully created {output_file_path}")

                except subprocess.CalledProcessError as e:
                    print(f"FFmpeg Error: {e}")
                    continue
                except Exception as e:
                    print(f"Error processing MPD {dash_file_path}: {e}")
                    continue

    for file in os.listdir(video_cache_folder):
        if file.lower().endswith(('.mp4', '.m4v')):
            videos.append({
                "name": file,
                "path": f"/video-cache/{file}"
            })

    # Sort videos alphabetically by name
    videos.sort(key=lambda x: x["name"])

    return jsonify(videos)

@app.route('/video-cache/<path:filename>')
def serve_video(filename):
    file_path = os.path.join('video-cache', filename)
    if not os.path.exists(file_path):
        abort(404, description=f"File not found: {filename}")
    
    def generate():
        with open(file_path, "rb") as video_file:
            while chunk := video_file.read(4096):
                yield chunk
    
    return Response(generate(), mimetype='video/mp4')

@app.route("/sync", methods=["POST"])
def sync_now():
    if ssh_enabled:
        print("Sync triggered manually.")
        try:
            Thread(target=sync_ssh_to_cache).start()
            return jsonify({"status": "success", "message": "Sync started successfully."}), 200
        except Exception as e:
            print(f"Error during sync: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    else:
        return jsonify({"status": "error", "message": "SSH is not enabled."}), 400
    

@app.route("/sync-status", methods=["GET"])
def get_sync_status():
    return jsonify({"syncing": syncing})


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

if __name__ == "__main__":

    # Make the server accessible to other devices
    app.run(host="0.0.0.0", port=5000)
