from flask import Flask, request, jsonify, send_file, render_template, make_response
import cv2
import numpy as np
import os
import hashlib
import time
from flask_cors import CORS
from dotenv import load_dotenv
import logging
from roboflow import Roboflow

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Initialize Roboflow API
rf = Roboflow(api_key="ZuZcnVQSkAnTImGMfqoW")
project = rf.workspace("absolute-foods-ownqh").project("tomato-disease-b518h")
model = project.version(3).model

UPLOAD_FOLDER = "./uploads"
PROCESSED_FOLDER = "./processed_videos"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

unique_images = set()

# Mapping of diseases to plant parts
disease_to_part = {
    "powdery_mildew": "leaf",
    "blight": "leaf",
    "rust": "stem",
    # Add more mappings based on your model's classes
}

def generate_hash(image):
    return hashlib.md5(image.tobytes()).hexdigest()

@app.route('/')
def index():
    logger.info("Rendering index.html at: %s", time.ctime())
    return render_template("index.html")

@app.route('/detect', methods=['POST'])
def detect():
    logger.info("Received request to /detect at: %s", time.ctime())
    if 'video' not in request.files or 'plant_type' not in request.form:
        logger.error("Missing video or plant type")
        return jsonify({"error": "Video and plant type are required"}), 400

    video_file = request.files['video']
    plant_type = request.form['plant_type']
    logger.info("Video file: %s, Plant type: %s", video_file.filename, plant_type)

    timestamp = int(time.time())
    video_path = os.path.join(UPLOAD_FOLDER, f"input_{timestamp}.mp4")
    logger.info("Saving video to: %s", video_path)
    video_file.save(video_path)

    processed_video_path = os.path.join(PROCESSED_FOLDER, f"processed_{timestamp}.mp4")
    logger.info("Processed video will be saved to: %s", processed_video_path)

    logger.info("Opening video with OpenCV...")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error("Failed to open video file")
        return jsonify({"error": "Failed to open video file"}), 500

    fps = int(cap.get(cv2.CAP_PROP_FPS))
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    logger.info("Video stats - FPS: %d, Width: %d, Height: %d, Total Frames: %d", fps, frame_width, frame_height, frame_count_total)

    fourcc = cv2.VideoWriter_fourcc(*'H264')
    out = cv2.VideoWriter(processed_video_path, fourcc, fps, (frame_width, frame_height))
    if not out.isOpened():
        logger.error("Failed to initialize video writer")
        cap.release()
        return jsonify({"error": "Failed to initialize video writer"}), 500

    frame_count = 0
    detected_diseases = []
    unique_images.clear()
    logger.info("Starting frame processing...")

    max_frames_to_process = 50  # Limit for testing
    while cap.isOpened() and frame_count < max_frames_to_process:
        ret, frame = cap.read()
        if not ret:
            logger.info("End of video reached after %d frames", frame_count)
            break

        # Process every 5th frame for detections
        if frame_count % 5 == 0:
            frame_resized = cv2.resize(frame, (640, 640), interpolation=cv2.INTER_AREA)
            logger.info("Processing frame %d...", frame_count)

            try:
                # Call Roboflow API to get predictions
                predictions = model.predict(frame_resized, confidence=0.43, overlap=0.5).json()
                logger.info("Roboflow predictions for frame %d: %s", frame_count, predictions)
                if "predictions" in predictions and predictions["predictions"]:
                    img_hash = generate_hash(frame_resized)

                    if img_hash not in unique_images:
                        unique_images.add(img_hash)
                        logger.info("New unique frame detected: %s", img_hash)

                        for pred in predictions["predictions"]:
                            # Scale coordinates from 640x640 to 480x848
                            scale_x = frame_width / 640.0  # 480 / 640 = 0.75
                            scale_y = frame_height / 640.0  # 848 / 640 = 1.325
                            x = int(pred["x"] * scale_x)
                            y = int(pred["y"] * scale_y)
                            w = int(pred["width"] * scale_x)
                            h = int(pred["height"] * scale_y)

                            label = pred["class"]
                            plant_part = disease_to_part.get(label.lower(), "unknown")
                            confidence = pred["confidence"]
                            logger.info("Disease detected - Frame: %d, Label: %s, Part: %s", frame_count, label, plant_part)

                            # Draw rectangle
                            top_left = (x - w // 2, y - h // 2)
                            bottom_right = (x + w // 2, y + h // 2)
                            cv2.rectangle(frame, top_left, bottom_right, (0, 255, 0), 2)

                            # Prepare text with more details
                            text = f"Frame {frame_count}: {label} on {plant_part} ({int(confidence * 100)}%)"
                            font = cv2.FONT_HERSHEY_SIMPLEX
                            font_scale = 0.6
                            thickness = 2
                            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                            text_x = x - w // 2
                            text_y = y - h // 2 - 10

                            # Draw a semi-transparent background box for the text
                            overlay = frame.copy()
                            cv2.rectangle(overlay, (text_x - 5, text_y - text_size[1] - 5), 
                                        (text_x + text_size[0] + 5, text_y + 5), (0, 0, 0), -1)
                            alpha = 0.5  # Transparency factor
                            cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

                            # Draw text on top of the background
                            cv2.putText(frame, text, (text_x, text_y), font, font_scale, (0, 255, 0), thickness)

                            detected_diseases.append({
                                "frame": frame_count,
                                "disease": label,
                                "plant_type": plant_type,
                                "plant_part": plant_part
                            })
            except Exception as e:
                logger.error("Error processing frame %d: %s", frame_count, str(e))
                cap.release()
                out.release()
                return jsonify({"error": str(e)}), 500

        # Write the frame to the output video *after* annotations are drawn
        logger.info("Writing frame %d to processed video...", frame_count)
        out.write(frame)

        frame_count += 1

    logger.info("Releasing video resources")
    cap.release()
    out.release()

    # Verify the processed video file exists
    if os.path.exists(processed_video_path):
        logger.info("Processed video saved successfully: %s", processed_video_path)
    else:
        logger.error("Processed video file not found: %s", processed_video_path)
        return jsonify({"error": "Failed to save processed video"}), 500

    logger.info("Processing complete. Detections: %s", detected_diseases)
    # Add timestamp to the video URL to prevent caching
    video_url = f"/get-latest-video?t={int(time.time())}"
    return jsonify({"processed_video": video_url, "detections": detected_diseases})

@app.route('/get-latest-video')
def get_latest_video():
    logger.info("Fetching latest processed video at: %s", time.ctime())
    processed_videos = sorted(os.listdir(PROCESSED_FOLDER), reverse=True)
    if processed_videos:
        latest_video_path = os.path.join(PROCESSED_FOLDER, processed_videos[0])
        logger.info("Sending video: %s", latest_video_path)
        mime_type = "video/mp4" if latest_video_path.endswith(".mp4") else "video/avi"
        response = make_response(send_file(os.path.abspath(latest_video_path), mimetype=mime_type))
        # Add cache-control headers to prevent caching
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    logger.error("No processed video found")
    return jsonify({"error": "No processed video found"}), 404

if __name__ == '__main__':
    logger.info("Starting Flask server at: %s", time.ctime())
    app.run(debug=True)