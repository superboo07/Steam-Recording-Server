import os
import json
import paramiko
import shutil
import subprocess
from flask import Flask, render_template, jsonify, abort, Response
from threading import Thread

app = Flask(__name__)

# Load config
with open("config.json", "r") as config_file:
    config = json.load(config_file)

local_recordings_folder = config["steam_recordings_folder"]
ssh_config = config.get("ssh", {})

ssh_enabled = ssh_config.get("enabled", False)
remote_recordings_folder = ssh_config.get("remote_path")
stream_cache_folder = os.path.join(os.getcwd(), "stream-cache")

# Function to sync SSH folder into /stream-cache/
def sync_ssh_to_cache():
    if not ssh_enabled:
        print("SSH sync is not enabled.")
        return

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
        )
        sftp = ssh.open_sftp()

        def recursive_copy(remote_dir, local_dir):
            os.makedirs(local_dir, exist_ok=True)
            items = sftp.listdir_attr(remote_dir)
            for item in items:
                remote_item = os.path.join(remote_dir, item.filename).replace("\\", "/")
                local_item = os.path.join(local_dir, item.filename)
                if item.st_mode & 0o040000:  # Directory
                    recursive_copy(remote_item, local_item)
                else:
                    print(f"Syncing file: {remote_item} to {local_item}")
                    sftp.get(remote_item, local_item)

        recursive_copy(remote_recordings_folder, stream_cache_folder)
        sftp.close()
        ssh.close()
        print("SSH sync completed successfully.")

    except Exception as e:
        print(f"SSH Sync Error: {e}")

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/videos")
def list_videos():
    videos = []
    video_cache_folder = os.path.join("video-cache")
    os.makedirs(video_cache_folder, exist_ok=True)

    # Use cache if SSH is enabled
    recordings_folder = stream_cache_folder if ssh_enabled else local_recordings_folder

    # Scan for DASH manifests
    for root, dirs, files in os.walk(recordings_folder):
        for file in files:
            if file == "session.mpd":
                dash_file_path = os.path.join(root, file)

                # Determine the naming logic based on the directory
                relative_path = os.path.relpath(root, recordings_folder)
                clip_path_parts = relative_path.split(os.sep)

                if "clips" in clip_path_parts:
                    # Naming logic for /clips/ path
                    clip_index = clip_path_parts.index("clips")
                    clip_name = "_".join(clip_path_parts[clip_index:])
                    output_file_name = f"{clip_name}.mp4"
                elif "video" in clip_path_parts:
                    # Naming logic for /video/ path
                    output_file_name = os.path.basename(os.path.dirname(dash_file_path)) + ".mp4"
                else:
                    # Skip if the file is not in a valid path
                    print(f"Skipping unrelated path: {dash_file_path}")
                    continue

                output_file_path = os.path.join(video_cache_folder, output_file_name)

                print(f"Found DASH file: {dash_file_path}")
                print(f"Output MP4 path: {output_file_path}")

                # Transcode to MP4 if not already cached
                if not os.path.exists(output_file_path):
                    print(f"Transcoding: {dash_file_path} to {output_file_path}")
                    ffmpeg_command = [
                        "ffmpeg", "-y", "-i", dash_file_path, "-c", "copy", output_file_path
                    ]
                    try:
                        subprocess.run(ffmpeg_command, check=True)
                        print(f"Successfully created {output_file_path}")
                    except subprocess.CalledProcessError as e:
                        print(f"FFmpeg error while processing {dash_file_path}: {e}")
                        continue

                # Add MP4 to the video list
                if os.path.exists(output_file_path):
                    videos.append({"name": output_file_name, "path": f"/video-cache/{output_file_name}"})
                else:
                    print(f"Failed to create MP4: {output_file_name}")
                    
    for file in os.listdir(video_cache_folder):
        if file.lower().endswith(('.mp4', '.m4v')):
            videos.append({
                "name": file,
                "path": f"/video-cache/{file}"
            })

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


@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

if __name__ == "__main__":
    # Automatically start sync on application startup
    if ssh_enabled:
        print("Starting initial sync...")
        Thread(target=sync_ssh_to_cache).start()

    # Make the server accessible to other devices
    app.run(debug=True, host="0.0.0.0", port=5000)
