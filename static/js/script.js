document.addEventListener("DOMContentLoaded", () => {
    const videoSelector = document.getElementById("videoSelector");
    const videoPlayer = document.getElementById("videoPlayer");
    const downloadButton = document.getElementById("downloadButton");

    // Fetch the list of videos
    fetch("/videos")
        .then(response => response.json())
        .then(videos => {
            videos.forEach(video => {
                const option = document.createElement("option");
                option.value = video.path; // Use the video path for playback and download
                option.textContent = video.name; // Show the folder name
                videoSelector.appendChild(option);
            });
        });

    // Enable download button when a video is selected
    videoSelector.addEventListener("change", () => {
        const selectedVideo = videoSelector.value;
        downloadButton.disabled = !selectedVideo;
        if (selectedVideo) {
            const player = dashjs.MediaPlayer().create();
            player.initialize(videoPlayer, `/stream/${selectedVideo}`, true);
        }
    });

    // Handle download button click
    downloadButton.addEventListener("click", () => {
        const selectedVideo = videoSelector.value;
        if (selectedVideo) {
            fetch("/mux", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ path: selectedVideo }),
            })
                .then(response => {
                    if (response.ok) {
                        return response.blob();
                    }
                    throw new Error("Failed to mux video.");
                })
                .then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = "output.mp4";
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                })
                .catch(error => {
                    console.error(error);
                    alert("Failed to download the video.");
                });
        }
    });
});
