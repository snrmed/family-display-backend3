# In backend/generator.py

import os
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image
from huggingface_hub import InferenceClient 
from google.cloud import storage 

# --- Configuration ---
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "your-unique-bucket-name")
HUGGING_FACE_TOKEN = os.environ.get("HUGGING_FACE_TOKEN") # Set in Cloud Run Job
AI_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
BASE_PROMPT = "A vibrant, cheerful, cartoon-style, high contrast sun or weather icon suitable for an e-ink display."


def generate_and_save_weekly_art():
    """Generates 7 images and saves them to Google Cloud Storage."""
    if not HUGGING_FACE_TOKEN:
        print("Error: HUGGING_FACE_TOKEN not set. Cannot generate AI art.")
        exit(1)

    # Initialize Clients
    hf_client = InferenceClient(token=HUGGING_FACE_TOKEN)
    storage_client = storage.Client()
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    
    # Calculate the start date of the coming week (The Monday date)
    today = datetime.now()
    # If today is Sunday (6), set start_date to tomorrow (Monday)
    # Otherwise, set to the next Monday
    start_date = today + timedelta(days=-today.weekday() + 7) 
    
    print(f"Starting weekly generation. Target week starts: {start_date.strftime('%Y-%m-%d')}")

    for day_index in range(7): # 0=Monday, 6=Sunday
        current_date = start_date + timedelta(days=day_index)
        day_name = current_date.strftime("%A")
        
        # Customize prompt for each day
        prompt = f"{BASE_PROMPT}. The theme is a {day_name} morning scene."

        try:
            # 2. Call Hugging Face API
            ai_image = hf_client.text_to_image(model=AI_MODEL, prompt=prompt)

            # 3. Convert PIL Image to Bytes
            img_byte_arr = BytesIO()
            ai_image.save(img_byte_arr, format='PNG') 
            img_byte_arr.seek(0)

            # 4. Define GCS file path and save
            # Path format: 'YYYY-MM-DD_dayindex.png'
            file_name = f"{start_date.strftime('%Y-%m-%d')}_{day_index}.png"
            blob = bucket.blob(f"weekly-art/{file_name}")
            blob.upload_from_file(img_byte_arr, content_type='image/png')
            
            print(f"Successfully saved image for {day_name} as {file_name}")

        except Exception as e:
            print(f"Failed to generate/save art for day {day_index} ({day_name}): {e}")
            continue 

if __name__ == '__main__':
    generate_and_save_weekly_art()
