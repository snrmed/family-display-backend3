import os
import requests
from flask import Flask, send_file, request, jsonify
from datetime import datetime, timedelta
from io import BytesIO

# Image processing libraries
from PIL import Image, ImageDraw, ImageFont

# Google Cloud Storage client
from google.cloud import storage

# --- CONFIGURATION ---
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480
FALLBACK_DIR = "backend/fallback_art"
FONT_PATH_BOLD = "backend/fonts/Roboto-Bold.ttf"
FONT_PATH_REGULAR = "backend/fonts/Roboto-Regular.ttf"

# Standard 6-Color E-Ink Palette (used for all drawing primitives)
EINK_PALETTE = {
    "BLACK": "#000000",
    "WHITE": "#FFFFFF",
    "RED": "#FF0000",
    "YELLOW": "#FFFF00",
    "BLUE": "#0000FF",
    "GREEN": "#00FF00" 
}
# E-Ink Palette as RGB tuples for Pillow's quantize function
EINK_COLOR_TUPLES = [
    (0, 0, 0),        # BLACK
    (255, 255, 255),  # WHITE
    (255, 0, 0),      # RED
    (255, 255, 0),    # YELLOW
    (0, 128, 0),      # GREEN (Using a common vibrant green)
    (0, 0, 255)       # BLUE
]


class FamilyDisplayApp:
    def __init__(self):
        self.app = Flask(__name__)
        self.gcs_bucket_name = os.environ.get("GCS_BUCKET_NAME")
        self.weather_api_key = os.environ.get("WEATHER_API_KEY")
        self.joke_api_url = os.environ.get("JOKE_API_URL")
        self.palette = EINK_PALETTE
        
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(self.gcs_bucket_name)

        # Mapping of variation index to drawing function
        self.drawing_functions = {
            0: self._draw_clean_clear_layout,
            1: self._draw_modern_pastel_layout,
            2: self._draw_cozy_cabin_layout,
            3: self._draw_sci_fi_glass_layout,
        }
        
        # Setup routes
        self.app.add_url_rule('/generate-display-image', view_func=self.generate_display_image, methods=['GET'])

    def get_font(self, path, size_large, size_small):
        """Helper to safely load a font."""
        try:
            return ImageFont.truetype(path, size_large), ImageFont.truetype(path, size_small)
        except IOError:
            print(f"WARNING: Could not load font from {path}. Using default.")
            return ImageFont.load_default(), ImageFont.load_default()

    # --- API FETCHERS ---

    def _fetch_weather(self, location: str):
        """Fetches current weather data."""
        # Split location to handle city, country format
        city = location.split(',')[0].strip()
        
        URL = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={self.weather_api_key}&units=metric"
        try:
            response = requests.get(URL, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            # Extract main weather info
            temp = int(data['main']['temp'])
            condition = data['weather'][0]['description'].capitalize()
            return f"{condition}, {temp}°C"
        except Exception as e:
            print(f"Weather fetch failed: {e}")
            return "Weather Unavailable"

    def _fetch_joke(self):
        """Fetches a random joke."""
        try:
            headers = {'Accept': 'application/json'}
            response = requests.get(self.joke_api_url, headers=headers, timeout=5)
            response.raise_for_status()
            joke_data = response.json()
            return joke_data.get('joke', "Why don't scientists trust atoms? Because they make up everything!")
        except Exception as e:
            print(f"Joke fetch failed: {e}")
            return "Joke Unavailable."

    # --- IMAGE QUANTIZATION ---

    def _quantize_to_eink_palette(self, img: Image.Image) -> Image.Image:
        """Converts an RGB image to the 6-color E-Ink palette using dithering."""
        
        # 1. Create a 256-color palette image using the 6 E-Ink colors
        palette_img = Image.new("P", (1, 1))
        
        palette_data = []
        for r, g, b in EINK_COLOR_TUPLES:
            palette_data.extend([r, g, b])
            
        # Pad the list to 768 (256 * 3)
        palette_data.extend([0] * (768 - len(palette_data))) 
        
        palette_img.putpalette(palette_data)
        
        # 2. Quantize the input image to this palette using Floyd-Steinberg dithering
        quantized_img = img.convert("RGB").quantize(
            palette=palette_img, 
            dither=Image.DITHER.FLOYDSTEINBERG
        )
        
        # Note: We return the RGB image *after* quantization, which now only 
        # contains the 6 supported colors (plus dithering approximations).
        return quantized_img.convert("RGB") 

    # --- FALLBACK LOGIC ---

    def _load_local_fallback(self, day_index: int, variation_index: int) -> Image.Image:
        """Loads a pre-baked local fallback image."""
        fallback_filename = f"{day_index}_{variation_index}.png"
        local_path = os.path.join(FALLBACK_DIR, fallback_filename)
        
        if os.path.exists(local_path):
            img = Image.open(local_path).convert("RGB")
            print(f"Successfully loaded local fallback: {local_path}")
            return img
        else:
            print("Local fallback image not found.")
            raise IOError("Local fallback missing.")

    def _fetch_stale_gcs_data(self, day_index: int, variation_index: int) -> Image.Image:
        """Scans GCS for any previously generated image matching the day and theme."""
        search_prefix = f"weekly-art/"
        target_suffix = f"_{day_index}_{variation_index}.png"
        
        try:
            blobs = self.bucket.list_blobs(prefix=search_prefix)
            
            stale_blob = None
            # Find the most recent (or any) file matching the pattern
            for blob in blobs:
                if blob.name.endswith(target_suffix):
                    stale_blob = blob
                    break # Found a match, use it
            
            if stale_blob:
                image_bytes = stale_blob.download_as_bytes()
                print(f"Successfully retrieved STALE image: {stale_blob.name}")
                return Image.open(BytesIO(image_bytes)).convert("RGB")
            
            raise Exception("No matching stale AI art found in GCS.") 

        except Exception as e:
            print(f"Stale GCS scan failed: {e}")
            raise Exception("Stale data recovery failed.")

    def fetch_ai_image(self, current_date: datetime, variation_index: int) -> Image.Image:
        """
        Fetches the image, trying Fresh GCS -> Local Fallback -> Stale GCS Data.
        The resulting image is always quantized to the 6-color palette.
        """
        start_of_week = current_date - timedelta(days=current_date.weekday())
        day_index = current_date.weekday() # 0=Monday, 6=Sunday
        
        # 1. Fresh Data Filename
        fresh_file_name = f"{start_of_week.strftime('%Y-%m-%d')}_{day_index}_{variation_index}.png"
        blob_path = f"weekly-art/{fresh_file_name}"

        img_to_quantize = None

        # --- Attempt 1: Fetch FRESH Data from GCS ---
        try:
            blob = self.bucket.blob(blob_path)
            image_bytes = blob.download_as_bytes()
            img_to_quantize = Image.open(BytesIO(image_bytes)).convert("RGB")
            print(f"Attempt 1 (Fresh GCS) Success: {fresh_file_name}")
            
        except Exception as e:
            print(f"Attempt 1 (Fresh GCS) Failed: {e}. Trying Attempt 2.")
            
            # --- Attempt 2: Load Local Fallback ---
            try:
                img_to_quantize = self._load_local_fallback(day_index, variation_index)
                print(f"Attempt 2 (Local Fallback) Success.")
                
            except IOError:
                print("Attempt 2 (Local Fallback) Failed. Trying Attempt 3.")
                
                # --- Attempt 3: Fetch STALE Data from GCS ---
                try:
                    img_to_quantize = self._fetch_stale_gcs_data(day_index, variation_index)
                    print(f"Attempt 3 (Stale GCS) Success.")

                except Exception as e:
                    print(f"Attempt 3 (Stale GCS) Failed: {e}. Displaying hardcoded error.")
                    
                    # --- Final Fallback: Hardcoded Placeholder (Last Resort) ---
                    img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color = self.palette['RED'])
                    d = ImageDraw.Draw(img)
                    font_large, _ = self.get_font(FONT_PATH_BOLD, 50, 20)
                    d.text((DISPLAY_WIDTH//2 - 150, DISPLAY_HEIGHT//2 - 50), "FATAL ERROR", fill=self.palette['WHITE'], font=font_large) 
                    return img
        
        # Quantize the successful image result (from any source)
        if img_to_quantize:
            return self._quantize_to_eink_palette(img_to_quantize)
        else:
            # Should not happen if logic is correct, but safe exit
            return Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color = self.palette['BLACK'])


    # --- DRAWING LAYOUTS ---
    
    # The drawing functions use the self.palette dictionary to ensure 
    # all colors are restricted to the 6-color set.

    def _draw_clean_clear_layout(self, data):
        """Variation 0: High contrast, geometric. White box, thick Red border."""
        d = data['draw']
        img = data['img']
        
        # Background: Use a light color
        d.rectangle((0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT), fill=self.palette['WHITE'])
        
        # Place AI Art (left side)
        img.paste(data['art'].resize((DISPLAY_WIDTH // 2, DISPLAY_HEIGHT)), (0, 0))
        
        # Info Box (White box with thick RED border on the right)
        box_x, box_y, box_w, box_h = DISPLAY_WIDTH * 0.52, 20, DISPLAY_WIDTH * 0.45, DISPLAY_HEIGHT - 40
        d.rectangle((box_x, box_y, box_x + box_w, box_y + box_h), fill=self.palette['WHITE'], outline=self.palette['RED'], width=5)
        
        # Text: Black
        text_x = box_x + 30
        d.text((text_x, 50), data['location'].upper().split(',')[0], fill=self.palette['BLACK'], font=data['fonts']['large'])
        d.text((text_x, 110), data['current_date'].strftime("%A, %b %d"), fill=self.palette['BLACK'], font=data['fonts']['medium'])
        
        # Weather
        weather_text = data['weather']
        d.text((text_x, 180), weather_text, fill=self.palette['BLACK'], font=data['fonts']['small'])
        
        # Separator Line: Black
        d.line((text_x, 230, box_x + box_w - 30, 230), fill=self.palette['BLACK'], width=3)
        
        # Joke (wrapped)
        joke_text = data['joke']
        d.text((text_x, 260), joke_text, fill=self.palette['BLACK'], font=data['fonts']['small'], align="left", spacing=4)
        
        return img

    def _draw_modern_pastel_layout(self, data):
        """Variation 1: Soft look using Yellow and Blue blocks."""
        d = data['draw']
        img = data['img']
        
        # Background and Box Colors
        BG_COLOR = self.palette['WHITE']
        BOX_COLOR = self.palette['YELLOW']
        TEXT_COLOR = self.palette['BLUE']
        
        # Background
        d.rectangle((0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT), fill=BG_COLOR)
        
        # Place AI Art (full width banner at top)
        art_height = DISPLAY_HEIGHT * 0.55
        img.paste(data['art'].resize((DISPLAY_WIDTH, art_height)), (0, 0))
        
        # Info Box (Full width box below art)
        box_x, box_y, box_w, box_h = 0, art_height, DISPLAY_WIDTH, DISPLAY_HEIGHT - art_height
        d.rectangle((box_x, box_y, box_x + box_w, box_y + box_h), fill=BOX_COLOR, outline=TEXT_COLOR, width=3)
        
        # Text layout (centered)
        center_x = DISPLAY_WIDTH // 2
        text_y_start = box_y + 20
        
        # Location
        loc_text = data['location'].upper().split(',')[0]
        loc_text_w = d.textlength(loc_text, font=data['fonts']['large'])
        d.text((center_x - loc_text_w / 2, text_y_start), loc_text, fill=TEXT_COLOR, font=data['fonts']['large'])
        
        # Date
        date_text = data['current_date'].strftime("%A, %b %d")
        date_text_w = d.textlength(date_text, font=data['fonts']['medium'])
        d.text((center_x - date_text_w / 2, text_y_start + 60), date_text, fill=TEXT_COLOR, font=data['fonts']['medium'])
        
        # Weather
        weather_text = data['weather']
        weather_text_w = d.textlength(weather_text, font=data['fonts']['small'])
        d.text((center_x - weather_text_w / 2, text_y_start + 110), weather_text, fill=TEXT_COLOR, font=data['fonts']['small'])
        
        # Separator Line: Blue
        d.line((100, text_y_start + 150, DISPLAY_WIDTH - 100, text_y_start + 150), fill=TEXT_COLOR, width=2)
        
        # Joke (wrapped and centered)
        joke_text = data['joke']
        # Note: Centering wrapped text is complex; keeping it left-aligned for simplicity here.
        d.text((100, text_y_start + 170), joke_text, fill=TEXT_COLOR, font=data['fonts']['small'], align="left", spacing=4)
        
        return img

    def _draw_cozy_cabin_layout(self, data):
        """Variation 2: Warm look using White, Red, and Green blocks."""
        d = data['draw']
        img = data['img']
        
        # Background and Box Colors (Simulating Red/Brown wood and White paper)
        BG_COLOR = self.palette['RED']
        TEXT_BOX = self.palette['WHITE'] 
        ACCENT_COLOR = self.palette['GREEN']
        
        # Background
        d.rectangle((0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT), fill=BG_COLOR)
        
        # Place AI Art (Right side banner)
        art_width = DISPLAY_WIDTH * 0.45
        img.paste(data['art'].resize((art_width, DISPLAY_HEIGHT)), (DISPLAY_WIDTH - art_width, 0))
        
        # Info Box (Left side, White box with Green border)
        box_x, box_y, box_w, box_h = 30, 30, DISPLAY_WIDTH * 0.5, DISPLAY_HEIGHT - 60
        d.rectangle((box_x, box_y, box_x + box_w, box_y + box_h), fill=TEXT_BOX, outline=ACCENT_COLOR, width=3)
        
        # Text: Black
        text_x = box_x + 20
        d.text((text_x, 50), data['location'].upper().split(',')[0], fill=self.palette['BLACK'], font=data['fonts']['large'])
        d.text((text_x, 120), data['current_date'].strftime("%A, %b %d"), fill=self.palette['BLACK'], font=data['fonts']['medium'])
        
        # Weather
        weather_text = data['weather']
        d.text((text_x, 200), weather_text, fill=self.palette['BLACK'], font=data['fonts']['small'])
        
        # Line: Green
        d.line((box_x + 10, 260, box_x + box_w - 10, 260), fill=ACCENT_COLOR, width=2)
        
        # Joke (wrapped)
        joke_text = data['joke']
        d.text((text_x, 280), joke_text, fill=self.palette['BLACK'], font=data['fonts']['small'], align="left", spacing=4)
        
        return img

    def _draw_sci_fi_glass_layout(self, data):
        """Variation 3: Futuristic look using Black, White, and Blue (Neon)."""
        d = data['draw']
        img = data['img']
        
        # Background: Black/Dark
        d.rectangle((0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT), fill=self.palette['BLACK'])
        
        # Place AI Art (full screen, darkened slightly by black BG)
        img.paste(data['art'].resize((DISPLAY_WIDTH, DISPLAY_HEIGHT)), (0, 0))

        # Info Box (Frosted Glass Look - semi-transparent white box, but we'll use a White box with Blue outline)
        box_x, box_y, box_w, box_h = 30, 30, DISPLAY_WIDTH - 60, DISPLAY_HEIGHT - 60
        
        # Draw a semi-transparent white box for the 'glass' effect. 
        # Since Pillow doesn't fully support transparency to RGB, we use a White box as a base.
        d.rectangle((box_x, box_y, box_x + box_w, box_y + box_h), fill=self.palette['WHITE'])
        
        # Draw Blue/Neon border
        d.rectangle((box_x, box_y, box_x + box_w, box_y + box_h), outline=self.palette['BLUE'], width=4)
        
        # Text: Black/White (using Black on the White box for best contrast)
        NEON_COLOR = self.palette['BLUE'] # Use Blue for accents
        TEXT_COLOR = self.palette['BLACK']
        
        text_x = box_x + 30
        
        d.text((text_x, 50), data['location'].upper().split(',')[0], fill=TEXT_COLOR, font=data['fonts']['large'])
        d.text((text_x, 120), data['current_date'].strftime("%A, %b %d"), fill=TEXT_COLOR, font=data['fonts']['medium'])
        
        # Weather
        weather_text = data['weather']
        d.text((text_x, 190), weather_text, fill=TEXT_COLOR, font=data['fonts']['small'])
        
        # Line: Blue
        d.line((text_x, 240, box_x + box_w - 30, 240), fill=NEON_COLOR, width=2)
        
        # Joke (wrapped)
        joke_text = data['joke']
        d.text((text_x, 260), joke_text, fill=TEXT_COLOR, font=data['fonts']['small'], align="left", spacing=4)
        
        return img
    
    # --- FLASK ROUTE ---

    def generate_display_image(self):
        """Main endpoint for device requests."""
        
        location = request.args.get('location', 'Sydney,AU')
        variation = request.args.get('variation', '0')
        
        try:
            variation_index = int(variation) % len(self.drawing_functions)
        except ValueError:
            variation_index = 0 # Default to Clean & Clear

        current_date = datetime.now()
        
        # 1. Fetch AI Art (with all fallbacks and quantization)
        ai_art = self.fetch_ai_image(current_date, variation_index)
        
        # 2. Fetch Dynamic Data
        weather = self._fetch_weather(location)
        joke = self._fetch_joke()
        
        # 3. Prepare Image Canvas
        final_img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color=self.palette['WHITE'])
        draw = ImageDraw.Draw(final_img)
        
        # 4. Load Fonts
        font_large, font_medium = self.get_font(FONT_PATH_BOLD, 40, 30)
        _, font_small = self.get_font(FONT_PATH_REGULAR, 15, 15)

        # 5. Prepare data dictionary for drawing function
        data = {
            'img': final_img,
            'draw': draw,
            'art': ai_art,
            'location': location,
            'current_date': current_date,
            'weather': weather,
            'joke': joke,
            'fonts': {
                'large': font_large,
                'medium': font_medium,
                'small': font_small,
            }
        }

        # 6. Apply the selected layout
        drawing_func = self.drawing_functions[variation_index]
        final_img = drawing_func(data)
        
        # 7. Convert to byte buffer and serve
        img_io = BytesIO()
        final_img.save(img_io, 'PNG')
        img_io.seek(0)
        
        return send_file(img_io, mimetype='image/png')


# --- RUN FLASK APP ---
if __name__ == '__main__':
    # Use Gunicorn as the production server entry point in Cloud Run
    # This block is mainly for local testing.
    app = FamilyDisplayApp().app
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
