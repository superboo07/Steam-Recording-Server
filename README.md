# Steam Recording Server

Most of this shit is AI generated code cause I did this at 3 AM and honestly cannot be bothered to learn interacting with SSH stuff in python, or how to host a webUI. Expecially for something thats both open source and not even strictly licensed. 

{
    "steam_recordings_folder": "/path/to/local/recordings",  // Path to the local steam recordings folder
    "ssh": {
        "enabled": false,  // Set to true if using SSH to sync recordings
        "host": "your.ssh.server",  // SSH server hostname or IP
        "port": 22,  // SSH server port (default is 22)
        "username": "your-username",  // SSH username
        "password": "your-password",  // SSH password
        "remote_path": "/path/to/remote/recordings"  // Path to the remote steam recordings folder
    }
}
