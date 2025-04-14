# Steam Recording Server

Most of this shit is AI generated code cause I did this at 3 AM and honestly cannot be bothered to learn interacting with SSH stuff in python, or how to host a webUI. Expecially for something thats both open source and not even strictly licensed. 

config.json:
```
{
    "steam_recordings_folder": "/path/to/local/recordings",
    "ssh": {
        "enabled": false,
        "host": "your.ssh.server",
        "port": 22,
        "username": "your-username",
        "password": "your-password",
        "remote_path": "/path/to/remote/recordings"
    }
}
```
