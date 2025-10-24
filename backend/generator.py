import os
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image
from huggingface_hub import InferenceClient 
from google.cloud import storage 

# --- Configuration ---
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "your-unique-bucket-name")
HUGGING_FACE_TOKEN = os.environ.get("HUGGING_FACE_TOKEN") 
AI_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"

# Prompts for the 4 themes (matching the index 0-3 in app.py)
THEME_PROMPTS = [
    "A highly structured, geometric, monochromatic, high contrast sun and cloud, perfect for e-ink display.",  # 0: Clean & Clear
    "A soft, abstract gradient, blurred focus, dreamy style, pastel colors, high contrast for e-ink display.",      # 1: Modern Pastel
    "A cute, hand-drawn, warm, inviting cartoon style sun and weather icon, high contrast for e-ink display.",    # 2: Cozy Cabin
    "A funny, wacky, surreal scene, unexpected weather, high contrast for e-ink display.",                      # 3: Sci-Fi Glass
]


def generate_and_save_weekly_art():
    """Generates 7 days * 4 themes = 28 images and saves them to Google Cloud Storage."""
    if not HUGGING_FACE_TOKEN:
        print("Error: HUGGING_FACE_TOKEN not set. Cannot generate AI art.")
        exit(1)

    # Initialize Clients
    hf_client = InferenceClient(token=HUGGING_FACE_TOKEN)
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    
    # Calculate the start date of the coming week (The Monday date)
    today = datetime.now()
    start_date = today + timedelta(days=-today.weekday() + 7) 
    
    print(f"Starting weekly generation. Target week starts: {start_date.strftime('%Y-%m-%d')}")

    for day_index in range(7): # 0=Monday, 6=Sunday
        current_date = start_date + timedelta(days=day_index)
        day_name = current_date.strftime("%A")

        for theme_index, base_prompt in enumerate(THEME_PROMPTS):
            
            # Combine base prompt with day specific detail
            prompt = f"{base_prompt}. The focus is on a {day_name} mood."

            try:
                # 1. Call Hugging Face API
                ai_image = hf_client.text_to_image(model=AI_MODEL, prompt=prompt)

                # 2. Convert PIL Image to Bytes
                img_byte_arr = BytesIO()
                ai_image.save(img_byte_arr, format='PNG') 
                img_byte_arr.seek(0)

                # 3. Define GCS file path and save (Format: YYYY-MM-DD_day_theme.png)
                file_name = f"{start_date.strftime('%Y-%m-%d')}_{day_index}_{theme_index}.png"
                blob = bucket.blob(f"weekly-art/{file_name}")
                blob.upload_from_file(img_byte_arr, content_type='image/png')
                
                print(f"Saved: {day_name} / Theme {theme_index} as {file_name}")

            except Exception as e:
                print(f"Failed to generate/save art for day {day_index}, theme {theme_index}: {e}")
                continue 

if __name__ == '__main__':
    generate_and_save_weekly_art()
