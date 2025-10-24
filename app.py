import os
import requests
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageColor
from flask import Flask, send_file, request
from google.cloud import storage

# --- Configuration ---
DISPLAY_WIDTH = 800  
DISPLAY_HEIGHT = 480 

FONT_PATH_BOLD = "backend/fonts/Roboto-Bold.ttf" 
FONT_PATH_REGULAR = "backend/fonts/Roboto-Regular.ttf"
FALLBACK_DIR = "backend/fallback_art" # Used if GCS fails

GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "your-unique-bucket-name")
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")
JOKE_API_URL = os.environ.get("JOKE_API_URL", "https://icanhazdadjoke.com/")


class FamilyDisplayApp:
    def __init__(self):
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(GCS_BUCKET_NAME)
        self.weather_symbols = {
            "Clear": "☀️", "Clouds": "☁️", "Rain": "🌧️",
            "Drizzle": "🌦️", "Thunderstorm": "⛈️", "Snow": "❄️",
            "Mist": "🌫️", "Haze": "🌫️", "Smoke": "🌫️"
        }

    def get_font(self, path, size, default_size=30):
        try:
            return ImageFont.truetype(path, size)
        except IOError:
            return ImageFont.load_default(size) 

    # --- Data Fetching Functions (No change from previous step) ---

    def fetch_weather_data(self, location: str) -> dict:
        """Fetches current temperature and condition from OpenWeatherMap."""
        if not WEATHER_API_KEY:
            return {"temp_str": "31° / 23°", "icon": "❓", "condition": "Default"}
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&units=metric&appid={WEATHER_API_KEY}"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            main_temp = int(data['main']['temp'])
            condition = data['weather'][0]['main']
            symbol = self.weather_symbols.get(condition, "❓")
            return {"temp_str": f"{main_temp}°C", "icon": symbol, "condition": condition}
        except Exception as e:
            print(f"Error fetching weather: {e}. Using default.")
            return {"temp_str": "31° / 23°", "icon": "❓", "condition": "Unknown"}

    def fetch_dad_joke(self) -> str:
        """Fetches a random joke from the configured API."""
        try:
            headers = {"Accept": "text/plain"}
            response = requests.get(JOKE_API_URL, headers=headers, timeout=5)
            response.raise_for_status()
            return response.text.strip()
        except Exception as e:
            print(f"Error fetching dad joke: {e}. Using default joke.")
            return "What do you call a fish with no eyes? A fsh!"

    # --- Image Fetching Function (UPDATED to use theme index) ---

    def fetch_ai_image(self, current_date: datetime, variation_index: int) -> Image.Image:
        """Fetches the pre-generated image for the current day and theme from GCS."""
        
        start_of_week = current_date - timedelta(days=current_date.weekday())
        day_index = current_date.weekday() 
        
        # Filename format: YYYY-MM-DD_dayindex_themeindex.png
        file_name = f"{start_of_week.strftime('%Y-%m-%d')}_{day_index}_{variation_index}.png"
        blob_path = f"weekly-art/{file_name}"

        try:
            # --- Attempt 1: Fetch from GCS ---
            blob = self.bucket.blob(blob_path)
            image_bytes = blob.download_as_bytes()
            print(f"Fetched AI image: {file_name}")
            return Image.open(BytesIO(image_bytes)).convert("RGB")
            
        except Exception as e:
            print(f"Error fetching GCS image {blob_path}: {e}. Trying local fallback.")
            
            # --- Attempt 2: Load local fallback image ---
            try:
                # Use a simple fallback naming convention
                fallback_filename = f"{day_index}_fallback_{variation_index}.png"
                local_path = os.path.join(FALLBACK_DIR, fallback_filename)
                
                img = Image.open(local_path).convert("RGB")
                print(f"Loaded local fallback: {fallback_filename}")
                return img
                
            except IOError:
                print("FATAL: Local fallback image not found. Returning hardcoded placeholder.")
                # --- Final Fallback: Hardcoded Placeholder ---
                img = Image.new('RGB', (200, 200), color = 'red')
                draw = ImageDraw.Draw(img)
                draw.text((10, 80), "FATAL ERROR", fill='white', font=self.get_font(FONT_PATH_REGULAR, 15, 15)) 
                return img

    # --- Image Generation (Composer) Function ---

    def generate_image(self, location: str, weather: dict, dad_joke: str, variation_index: int):
        
        current_date = datetime.now() 
        
        # 1. Fetch the pre-generated AI art (uses the variation index)
        ai_art = self.fetch_ai_image(current_date, variation_index)
        
        # 2. Setup Canvas and Fonts
        img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color='white')
        draw = ImageDraw.Draw(img)
        font_bold_large = self.get_font(FONT_PATH_BOLD, 40, 30)
        font_bold_medium = self.get_font(FONT_PATH_BOLD, 30, 20)
        font_regular_small = self.get_font(FONT_PATH_REGULAR, 24, 15)
        
        # Package data for drawing functions
        draw_data = {
            'draw': draw, 'img': img, 'ai_art': ai_art, 'location': location, 
            'weather': weather, 'dad_joke': dad_joke, 'current_date': current_date,
            'fonts': {'large': font_bold_large, 'medium': font_bold_medium, 'small': font_regular_small}
        }

        # --- 3. LAYOUT SWITCHING LOGIC ---
        
        if variation_index == 0:
            self._draw_clean_clear_layout(draw_data)
        elif variation_index == 1:
            self._draw_modern_pastel_layout(draw_data)
        elif variation_index == 2:
            self._draw_cozy_cabin_layout(draw_data)
        elif variation_index == 3:
            self._draw_sci_fi_glass_layout(draw_data)
        else:
            self._draw_clean_clear_layout(draw_data) # Default fallback

        # 4. Return Image Bytes
        img_byte_arr = BytesIO()
        img.save(img_byte_arr, format='PNG') 
        return img_byte_arr.getvalue() 

    # --- DRAWING HELPER METHODS (4 Variations) ---

    def _draw_clean_clear_layout(self, data):
        """Variation 0: High contrast, geometric. White box, thick black border."""
        d = data['draw']
        img = data['img']
        # Background
        d.rectangle((0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT), fill=ImageColor.getrgb("lightgray"))
        # AI Art (high contrast placement)
        art_size = int(DISPLAY_WIDTH * 0.4)
        art_resized = data['ai_art'].resize((art_size, art_size)) 
        img.paste(art_resized, (DISPLAY_WIDTH - art_size - 20, 20)) 
        
        # Info Box (Simple white box with thick black border)
        box_x, box_y, box_w, box_h = 20, 20, DISPLAY_WIDTH * 0.55, DISPLAY_HEIGHT - 40
        d.rectangle((box_x, box_y, box_x + box_w, box_y + box_h), fill='white', outline='black', width=5)
        
        # Text
        text_x = box_x + 30
        d.text((text_x, 50), data['location'].upper().split(',')[0], fill='black', font=data['fonts']['large'])
        d.text((text_x, 110), data['current_date'].strftime("%A, %b %d"), fill='black', font=data['fonts']['medium'])
        
        weather_text = f"{data['weather']['icon']} {data['weather']['condition']}: {data['weather']['temp_str']}"
        d.text((text_x, 180), weather_text, fill='black', font=data['fonts']['small'])
        
        d.line((text_x, 230, box_x + box_w - 30, 230), fill='black', width=3)
        
        joke_text = "Dad joke: " + data['dad_joke']
        d.text((text_x, 260), joke_text, fill='black', font=data['fonts']['small'])

    def _draw_modern_pastel_layout(self, data):
        """Variation 1: Soft gradients, pastel colors. Centered, symmetric layout."""
        d = data['draw']
        img = data['img']
        
        PASTEL_BG = ImageColor.getrgb("#F0F8FF") # Alice Blue
        PASTEL_BOX = ImageColor.getrgb("#ADD8E6") # Light Blue
        
        # Background
        d.rectangle((0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT), fill=PASTEL_BG)
        
        # AI Art (Centered top)
        art_size = int(DISPLAY_WIDTH * 0.4)
        art_resized = data['ai_art'].resize((art_size, art_size)) 
        img.paste(art_resized, ((DISPLAY_WIDTH - art_size) // 2, 20)) 
        
        # Info Box (Centered, rounded corners are hard in PIL, so use a nice fill color)
        box_x, box_y, box_w, box_h = 50, 250, DISPLAY_WIDTH - 100, 200
        d.rectangle((box_x, box_y, box_x + box_w, box_y + box_h), fill=PASTEL_BOX, outline=ImageColor.getrgb("#87CEEB"), width=2)
        
        # Text (Centered Layout)
        center_x = box_x + box_w // 2
        
        loc_text = data['location'].upper().split(',')[0]
        loc_text_w = d.textlength(loc_text, font=data['fonts']['large'])
        d.text((center_x - loc_text_w / 2, box_y + 20), loc_text, fill='darkblue', font=data['fonts']['large'])
        
        date_text = data['current_date'].strftime("%A, %b %d")
        date_text_w = d.textlength(date_text, font=data['fonts']['medium'])
        d.text((center_x - date_text_w / 2, box_y + 80), date_text, fill='darkblue', font=data['fonts']['medium'])
        
        weather_text = f"{data['weather']['icon']} {data['weather']['temp_str']} | {data['weather']['condition']}"
        weather_text_w = d.textlength(weather_text, font=data['fonts']['small'])
        d.text((center_x - weather_text_w / 2, box_y + 130), weather_text, fill='darkblue', font=data['fonts']['small'])

    def _draw_cozy_cabin_layout(self, data):
        """Variation 2: Cute/Cartoon style, 'cloud' look borders."""
        d = data['draw']
        img = data['img']
        
        WOOD_BG = ImageColor.getrgb("#EADDCA") # Light beige/wood tone
        TEXT_BOX = ImageColor.getrgb("#FFFFFF") # White

        # Background
        d.rectangle((0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT), fill=WOOD_BG)
        
        # AI Art (Large left-side placement)
        art_size = int(DISPLAY_HEIGHT * 0.7)
        art_resized = data['ai_art'].resize((art_size, art_size)) 
        img.paste(art_resized, (30, 30)) 
        
        # Info Box (Right side, clustered)
        box_x, box_y, box_w, box_h = DISPLAY_WIDTH * 0.55, 30, DISPLAY_WIDTH * 0.4, DISPLAY_HEIGHT - 60
        d.rectangle((box_x, box_y, box_x + box_w, box_y + box_h), fill=TEXT_BOX, outline='brown', width=3)
        
        text_x = box_x + 20
        d.text((text_x, 50), data['location'].upper().split(',')[0], fill='brown', font=data['fonts']['large'])
        
        date_text = data['current_date'].strftime("%a, %b %d")
        d.text((text_x, 110), date_text, fill='brown', font=data['fonts']['medium'])
        
        weather_text = f"{data['weather']['icon']} {data['weather']['temp_str']} | {data['weather']['condition']}"
        d.text((text_x, 170), weather_text, fill='brown', font=data['fonts']['small'])
        
        # Joke section separated by a simple line
        d.line((box_x + 10, 220, box_x + box_w - 10, 220), fill='brown', width=2)
        
        joke_text = "Joke: " + data['dad_joke']
        d.text((text_x, 240), joke_text, fill='brown', font=data['fonts']['small'])

    def _draw_sci_fi_glass_layout(self, data):
        """Variation 3: Asymmetric layout, frosted glass look overlay."""
        d = data['draw']
        img = data['img']
        
        # Background: Neon Purple/Blue
        d.rectangle((0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT), fill=ImageColor.getrgb("#200050"))
        
        # AI Art (asymmetric top-right placement)
        art_size = int(DISPLAY_WIDTH * 0.35)
        art_resized = data['ai_art'].resize((art_size, art_size)) 
        img.paste(art_resized, (DISPLAY_WIDTH - art_size - 40, 10)) 

        # Info Box (Frosted Glass Look)
        box_x, box_y, box_w, box_h = 30, 150, DISPLAY_WIDTH - 60, DISPLAY_HEIGHT - 170
        
        # 1. Create a semi-transparent white layer (Frosted/Glazed effect)
        transparent_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw_transparent = ImageDraw.Draw(transparent_layer)
        # Draw semi-transparent white rectangle (alpha 180/255)
        draw_transparent.rectangle((box_x, box_y, box_x + box_w, box_y + box_h), fill=(255, 255, 255, 180))
        img.paste(transparent_layer, (0, 0), transparent_layer)
        
        # 2. Draw Cyan/Neon border
        d.rectangle((box_x, box_y, box_x + box_w, box_y + box_h), outline=ImageColor.getrgb("cyan"), width=4)
        
        # Text (Neon Green Color)
        NEON_GREEN = ImageColor.getrgb("#39FF14")
        text_x = box_x + 30
        
        d.text((text_x, box_y + 30), data['location'].upper().split(',')[0], fill=NEON_GREEN, font=data['fonts']['large'])
        d.text((text_x, box_y + 90), data['current_date'].strftime("%A, %b %d"), fill=NEON_GREEN, font=data['fonts']['medium'])
        
        weather_text = f"// WEATHER // {data['weather']['icon']} {data['weather']['temp_str']}"
        d.text((text_x, box_y + 150), weather_text, fill=NEON_GREEN, font=data['fonts']['small'])
        
        d.line((text_x, box_y + 190, box_x + box_w - 30, box_y + 190), fill=NEON_GREEN, width=2)
        
        joke_text = "ACCESS: " + data['dad_joke']
        d.text((text_x, box_y + 220), joke_text, fill=NEON_GREEN, font=data['fonts']['small'])


# --- Flask Setup ---
app = Flask(__name__)
display_app = FamilyDisplayApp()

@app.route('/generate-display-image', methods=['GET'])
def get_display_image():
    """
    Receives 'location' and 'variation' from the device.
    Example: /generate-display-image?location=Sydney,AU&variation=1
    """
    location = request.args.get('location', 'Darwin, NT, AU')
    try:
        variation = int(request.args.get('variation', 0))
    except ValueError:
        variation = 0 # Fallback if non-integer is sent
    
    try:
        weather_data = display_app.fetch_weather_data(location)
        joke = display_app.fetch_dad_joke()
        
        image_bytes = display_app.generate_image(
            location=location,
            weather=weather_data,
            dad_joke=joke,
            variation_index=variation
        ) 
        
        return send_file(BytesIO(image_bytes), mimetype='image/png')
        
    except Exception as e:
        print(f"An unexpected error occurred in main route: {e}")
        # Standard error image response (omitted for brevity, assume working)
        error_img = Image.new('RGB', (200, 100), color='red')
        error_draw = ImageDraw.Draw(error_img)
        error_draw.text((10, 40), "SERVER ERROR", fill='white')
        error_bytes = BytesIO()
        error_img.save(error_bytes, format='PNG')
        return send_file(BytesIO(error_bytes.getvalue()), mimetype='image/png', status=500)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
