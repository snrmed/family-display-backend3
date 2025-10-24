# In backend/app.py, inside the FamilyDisplayApp class

# Path to the fallback directory
FALLBACK_DIR = "backend/fallback_art"

def fetch_ai_image(self, current_date: datetime, variation_index: int) -> Image.Image:
    """Fetches image, trying fresh GCS, local fallback, and finally, stale GCS data."""
    
    start_of_week = current_date - timedelta(days=current_date.weekday())
    day_index = current_date.weekday() 
    
    # GCS Filename: YYYY-MM-DD_dayindex_themeindex.png
    fresh_file_name = f"{start_of_week.strftime('%Y-%m-%d')}_{day_index}_{variation_index}.png"
    blob_path = f"weekly-art/{fresh_file_name}"

    try:
        # --- Attempt 1: Fetch FRESH Data from GCS ---
        blob = self.bucket.blob(blob_path)
        image_bytes = blob.download_as_bytes()
        print(f"Successfully fetched fresh AI image: {fresh_file_name}")
        return Image.open(BytesIO(image_bytes)).convert("RGB")
        
    except Exception as e:
        print(f"GCS Error ({fresh_file_name}): {e}. Trying local fallback.")
        
        # --- Attempt 2: Load local fallback image ---
        try:
            fallback_filename = f"{day_index}_{variation_index}.png"
            local_path = os.path.join(FALLBACK_DIR, fallback_filename)
            img = Image.open(local_path).convert("RGB")
            print(f"Successfully loaded local fallback: {local_path}")
            return img
            
        except IOError:
            print("Local fallback not found. Trying STALE data from GCS.")
            
            # --- Attempt 3: Fetch STALE Data from GCS ---
            try:
                # Prefix to search for ALL files matching the day and theme, regardless of date
                search_prefix = f"weekly-art/"
                
                # List blobs with a prefix, sorted by creation time (newest first is preferred)
                blobs = self.bucket.list_blobs(prefix=search_prefix)
                
                # Use a filter that looks for the required day_index and theme_index
                target_suffix = f"_{day_index}_{variation_index}.png"
                
                stale_blob = None
                
                # We iterate through the list of all files in GCS, looking for the first 
                # file that matches the required day and theme.
                for blob in blobs:
                    if blob.name.endswith(target_suffix):
                        stale_blob = blob
                        break  # Found the first (or oldest, depending on GCS listing) match
                
                if stale_blob:
                    image_bytes = stale_blob.download_as_bytes()
                    print(f"Successfully retrieved STALE image: {stale_blob.name}")
                    return Image.open(BytesIO(image_bytes)).convert("RGB")
                
                # If the loop finishes without finding anything
                raise Exception("No matching stale AI art found in GCS.") 

            except Exception as e:
                print(f"FATAL: Stale GCS scan failed: {e}. Displaying hardcoded error.")
                
                # --- Final Fallback: Hardcoded Placeholder (Last Resort) ---
                img = Image.new('RGB', (200, 200), color = 'red')
                draw = ImageDraw.Draw(img)
                font = self.get_font(FONT_PATH_REGULAR, 15, 15) 
                draw.text((10, 80), "FATAL ERROR", fill='white', font=font) 
                return img
