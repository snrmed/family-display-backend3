# In backend/app.py, inside the FamilyDisplayApp class

# Path to the fallback directory (relative to the container's working dir /app)
FALLBACK_DIR = "backend/fallback_art"

def fetch_ai_image(self, current_date: datetime, variation_index: int) -> Image.Image:
    """Fetches the pre-generated image for the current day and theme from GCS, 
       falling back to a local file if GCS fails."""
    
    start_of_week = current_date - timedelta(days=current_date.weekday())
    day_index = current_date.weekday() 
    
    # GCS Filename: YYYY-MM-DD_dayindex_themeindex.png
    file_name = f"{start_of_week.strftime('%Y-%m-%d')}_{day_index}_{variation_index}.png"
    blob_path = f"weekly-art/{file_name}"

    try:
        # --- Attempt 1: Fetch from GCS ---
        blob = self.bucket.blob(blob_path)
        image_bytes = blob.download_as_bytes()
        print(f"Successfully fetched AI image: {file_name}")
        return Image.open(BytesIO(image_bytes)).convert("RGB")
        
    except Exception as e:
        print(f"Error fetching GCS image {blob_path}: {e}. Trying local fallback.")
        
        # --- Attempt 2: Load local fallback image ---
        try:
            # Construct the local path: dayindex_themeindex.png
            fallback_filename = f"{day_index}_{variation_index}.png"
            local_path = os.path.join(FALLBACK_DIR, fallback_filename)
            
            # The Dockerfile ensures this path is correct inside the container
            img = Image.open(local_path).convert("RGB")
            print(f"Successfully loaded local fallback: {local_path}")
            return img
            
        except IOError:
            print("FATAL: Local fallback image not found. Returning hardcoded placeholder.")
            # --- Final Fallback: Hardcoded Placeholder (as a last resort) ---
            img = Image.new('RGB', (200, 200), color = 'red')
            draw = ImageDraw.Draw(img)
            # Ensure font is available for the final placeholder
            font = self.get_font(FONT_PATH_REGULAR, 15, 15) 
            draw.text((10, 80), "FATAL ERROR", fill='white', font=font) 
            return img
