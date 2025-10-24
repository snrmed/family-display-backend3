import os
import requests
import json
from datetime import datetime, timedelta
from io import BytesIO

# Configuration
HUGGING_FACE_TOKEN = os.environ.get("HUGGING_FACE_TOKEN")
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME")
AI_MODEL_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-2-1"

# The Google Cloud Storage client needs to be imported here
from google.cloud import storage
storage_client = storage.Client()

# Prompts for the 4 themes (matching the index 0-3 in app.py)
# Optimized for 6-Color E-Ink: Limited palette, solid colors, and high contrast.
THEME_PROMPTS = [
    # 0: Clean & Clear (Geometric, Minimal, Monochromatic/Limited Color)
    "A stunning scene of a sunrise over a cityscape, rendered in bold **geometric** shapes and hard lines, using a **limited 6-color palette** of Black, White, and one primary color. Use **solid color blocks** and avoid complex gradients, designed for e-ink display. The overall composition captures the feeling of a **{day_name} morning**.",
    
    # 1: Modern Pastel (Abstract, Soft Gradients, Dreamy - Modified to use blocks)
    "An **abstract, semi-flat** landscape view, focusing on soft, **dreamy pastel** colors. Render the image using **limited 6-color blocks** instead of gradients, high contrast. The composition should suggest atmospheric weather using layered color shapes, optimized for e-ink display. The scene reflects the ambiance of a **{day_name} morning**.",
    
    # 2: Cozy Cabin (Cute/Cartoon, Hand-Drawn, Warm)
    "A cozy, **Studio Ghibli-inspired** scene looking out a window at the weather. **Hand-drawn, cute cartoon** style with a **limited 6-color palette**. Use thick outlines and **solid color fills** (e.g., warm yellows and reds) to depict the comfort of a **{day_name} morning**, optimized for e-ink display.",
    
    # 3: Sci-Fi Glass (Funny/Wacky, Surreal, Futuristic, Neon)
    "A **surreal and wacky** futuristic cityscape where the weather is manufactured. Style is **cyberpunk/neon** using only **three distinct colors** (e.g., Black, White, and Cyan/Magenta). Use **solid color fields** and bold lines to depict the scene's extreme contrast, optimized for e-ink display. The image captures the strange energy of a **{day_name} morning**."
]

def query_hugging_face(prompt: str) -> bytes:
    """Sends a prompt to the Hugging Face API and returns the raw image bytes."""
    headers = {"Authorization": f"Bearer {HUGGING_FACE_TOKEN}"}
    payload = {"inputs": prompt}
    
    print(f"Querying AI with prompt: {prompt}")
    response = requests.post(AI_MODEL_URL, headers=headers, json=payload)
    
    # Check if the response is valid image data (not JSON error)
    if response.headers.get('Content-Type') != 'image/jpeg':
        try:
            error_data = response.json()
            raise Exception(f"AI API Error: {error_data.get('error', 'Unknown error')}")
        except json.JSONDecodeError:
            raise Exception(f"AI API Error: Received status code {response.status_code}")
            
    return response.content

def upload_to_gcs(file_name: str, image_bytes: bytes):
    """Uploads the image bytes to the GCS bucket."""
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(f"weekly-art/{file_name}")
    
    blob.upload_from_file(BytesIO(image_bytes), content_type='image/png') # Use PNG for better quality/e-ink compatibility
    print(f"Successfully uploaded {file_name} to GCS.")

def generate_weekly_art():
    """Generates 7 days x 4 themes of art and uploads them to GCS."""
    if not HUGGING_FACE_TOKEN or not GCS_BUCKET_NAME:
        print("FATAL ERROR: HUGGING_FACE_TOKEN or GCS_BUCKET_NAME environment variable is missing.")
        return

    # Calculate the start of the NEXT week (assuming job runs on Sunday for the coming week)
    today = datetime.now().date()
    # Calculate the date of the coming Monday (day index 0)
    days_until_monday = (7 - today.weekday() + 0) % 7
    start_of_week = today + timedelta(days=days_until_monday) 
    
    print(f"Starting art generation for the week of: {start_of_week.strftime('%Y-%m-%d')}")

    # Generate art for 7 days (Monday=0 to Sunday=6)
    for day_index in range(7):
        current_date = start_of_week + timedelta(days=day_index)
        day_name = current_date.strftime("%A")

        for theme_index in range(len(THEME_PROMPTS)):
            base_prompt = THEME_PROMPTS[theme_index]
            final_prompt = base_prompt.format(day_name=day_name)
            
            # Filename format: YYYY-MM-DD_dayindex_themeindex.png
            file_name = f"{current_date.strftime('%Y-%m-%d')}_{day_index}_{theme_index}.png"

            try:
                image_bytes = query_hugging_face(final_prompt)
                upload_to_gcs(file_name, image_bytes)
                print(f"✅ Success: {file_name}")
                
            except Exception as e:
                print(f"❌ Failed to generate/upload {file_name}: {e}. Skipping.")
                # IMPORTANT: If AI generation fails, the Composer Service will fall back
                # to the local fallback_art or stale GCS data.

if __name__ == "__main__":
    generate_weekly_art()
