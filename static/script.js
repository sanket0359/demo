async function uploadVideo() {
    console.log("Step 1: Upload button clicked at:", new Date().toISOString());

    // Verify DOM elements
    const fileInput = document.getElementById("videoUpload");
    const plantTypeSelect = document.getElementById("plantType");
    const spinner = document.getElementById("spinner");
    const detectionConsole = document.getElementById("detectionConsole");
    const videoPreview = document.getElementById("videoPreview");
    const videoPreviewSource = document.getElementById("videoPreviewSource");
    const processedVideo = document.getElementById("processedVideo");
    const processedVideoSource = document.getElementById("processedVideoSource");

    console.log("Step 2: Checking DOM elements...");
    if (!fileInput || !plantTypeSelect || !spinner || !detectionConsole || !videoPreview || !videoPreviewSource || !processedVideo || !processedVideoSource) {
        console.error("DOM elements missing:", {
            fileInput: !!fileInput,
            plantTypeSelect: !!plantTypeSelect,
            spinner: !!spinner,
            detectionConsole: !!detectionConsole,
            videoPreview: !!videoPreview,
            videoPreviewSource: !!videoPreviewSource,
            processedVideo: !!processedVideo,
            processedVideoSource: !!processedVideoSource
        });
        alert("Error: UI elements are missing. Please check the page structure.");
        return;
    }

    const plantType = plantTypeSelect.value;
    console.log("Step 3: Validating inputs...");
    if (!fileInput.files[0]) {
        console.log("No video selected");
        alert("Please select a video.");
        return;
    }
    if (!plantType) {
        console.log("No plant type selected");
        alert("Please select a plant type.");
        return;
    }

    console.log("Step 4: Video and plant type selected:", fileInput.files[0].name, plantType);
    const formData = new FormData();
    formData.append("video", fileInput.files[0]);
    formData.append("plant_type", plantType);
    console.log("Step 5: FormData prepared:", [...formData.entries()]);

    console.log("Step 6: Setting video preview...");
    videoPreviewSource.src = URL.createObjectURL(fileInput.files[0]);
    videoPreview.load();
    spinner.style.display = "block";
    detectionConsole.innerText = "Processing...";
    console.log("Step 7: UI updated with spinner and processing message");

    try {
        console.log("Step 8: Sending fetch request to /detect...");
        const response = await fetch("/detect", {
            method: "POST",
            body: formData,
        });
        console.log("Step 9: Fetch response received - Status:", response.status, "StatusText:", response.statusText);

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const result = await response.json();
        console.log("Step 10: Fetch response JSON:", result);

        console.log("Step 11: Hiding spinner...");
        spinner.style.display = "none";

        if (result.error) {
            console.error("Backend error:", result.error);
            detectionConsole.innerText = `Error: ${result.error}`;
            console.log("Step 12: UI updated with backend error");
            return;
        }

        console.log("Step 13: Setting processed video...");
        processedVideoSource.src = result.processed_video || "";
        console.log("Processed video source src set to:", processedVideoSource.src);

        // Add error listener for video playback
        processedVideo.addEventListener('error', (e) => {
            console.error("Video playback error:", e);
            console.error("Video error code:", processedVideo.error ? processedVideo.error.code : 'Unknown');
            console.error("Video error message:", processedVideo.error ? processedVideo.error.message : 'Unknown');
            detectionConsole.innerText += "\nError: Failed to play processed video. Check browser console for details.";
        });

        // Add loadeddata listener to confirm video is ready
        processedVideo.addEventListener('loadeddata', () => {
            console.log("Processed video loaded successfully, attempting to play...");
            processedVideo.play().catch(err => {
                console.error("Error playing video:", err);
                detectionConsole.innerText += "\nError: Could not play video automatically. Try clicking play.";
            });
        });

        processedVideo.load();  // Force the video to load
        console.log("Step 14: Video load triggered");

        console.log("Step 15: Processing detections...");
        const detections = result.detections.map(d => 
            `Frame ${d.frame}: ${d.disease} detected on ${d.plant_part} of ${d.plant_type} plant`
        ).join("\n");
        console.log("Step 16: Detections prepared:", detections);
        detectionConsole.innerText = detections || "No diseases detected.";
        console.log("Step 17: UI updated with detections");

    } catch (error) {
        console.error("Fetch error:", error);
        spinner.style.display = "none";
        detectionConsole.innerText = `Error: ${error.message}`;
        console.log("Step 18: Error handled and UI updated with error message");
    }
}