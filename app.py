import os
import requests
from datetime import datetime, timedelta
from io import BytesIO

# Third-party libraries
from PIL import Image, ImageDraw, ImageFont 
from flask import Flask, send_file, request
from google.cloud import storage

# --- Configuration (Adjust for your 800x480 display) ---
DISPLAY_WIDTH = 800  
DISPLAY_HEIGHT = 480 

# Paths relative to the container's working directory (/app)
FONT_PATH_BOLD = "backend/fonts/Roboto-Bold.ttf" 
FONT_PATH_REGULAR = "backend/fonts/Roboto-Regular.ttf"

# Environment Variables needed for this service (set in Cloud Run GUI)
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "your-unique-bucket-name")
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")
JOKE_API_URL = os.environ.get("JOKE_API_URL", "https://icanhazdadjoke.com/")


class FamilyDisplayApp:
    def __init__(self):
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(GCS_BUCKET_NAME)
        # Simple weather symbols mapping
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

    # --- Data Fetching Functions ---

    def fetch_weather_data(self, location: str) -> dict:
        """Fetches current temperature and condition from OpenWeatherMap."""
        if not WEATHER_API_KEY:
            return {"temp_str": "31° / 23°", "icon": "❓", "condition": "Default"}

        try:
            url = (
                f"http://api.openweathermap.org/data/2.5/weather?q={location}"
                f"&units=metric&appid={WEATHER_API_KEY}"
            )
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            main_temp = int(data['main']['temp'])
            min_temp = int(data['main']['temp_min'])
            # condition is capitalized, e.g., "Clouds"
            condition = data['weather'][0]['main'] 
            
            symbol = self.weather_symbols.get(condition, "❓")
            
            return {
                "temp_str": f"{main_temp}°C",
                "icon": symbol,
                "condition": condition
            }

        except Exception as e:
            print(f"Error fetching weather for {location}: {e}. Using default.")
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

    # --- Image Fetching Function ---

    def fetch_ai_image(self, current_date: datetime) -> Image.Image:
        """Fetches the pre-generated image for the current day from GCS."""
        
        # Calculate the start date of the current batch (Monday's date)
        start_of_week = current_date - timedelta(days=current_date.weekday())
        day_index = current_date.weekday() # 0=Monday, 6=Sunday
        
        # Format: 'YYYY-MM-DD_dayindex.png'
        file_name = f"{start_of_week.strftime('%Y-%m-%d')}_{day_index}.png"
        blob_path = f"weekly-art/{file_name}"

        try:
            blob = self.bucket.blob(blob_path)
            image_bytes = blob.download_as_bytes()
            return Image.open(BytesIO(image_bytes)).convert("RGB")
            
        except Exception as e:
            print(f"Error fetching GCS image {blob_path}: {e}. Returning simple placeholder.")
            img = Image.new('RGB', (200, 200), color = 'red')
            draw = ImageDraw.Draw(img)
            draw.text((10, 80), "GCS ERROR", fill='white', font=self.get_font(FONT_PATH_REGULAR, 15, 15)) 
            return img


    # --- Image Generation (Composer) Function ---

    def generate_image(self, location: str, weather: dict, dad_joke: str):
        
        current_date = datetime.now() 
        
        # 1. Fetch the pre-generated AI art
        ai_art = self.fetch_ai_image(current_date)
        
        # 2. Setup Canvas and Fonts
        img = Image.new('RGB', (DISPLAY_WIDTH, DISPLAY_HEIGHT), color='white')
        draw = ImageDraw.Draw(img)
        font_bold_large = self.get_font(FONT_PATH_BOLD, 40, 30)
        font_bold_medium = self.get_font(FONT_PATH_BOLD, 30, 20)
        font_regular_small = self.get_font(FONT_PATH_REGULAR, 24, 15)

        # 3. Drawing Elements (Visual Layout)
        
        SKY_COLOR = (135, 206, 250) 
        GRASS_COLOR = (144, 238, 144) 
        draw.rectangle((0, 0, DISPLAY_WIDTH, DISPLAY_HEIGHT * 0.5), fill=SKY_COLOR)
        draw.rectangle((0, DISPLAY_HEIGHT * 0.5, DISPLAY_WIDTH, DISPLAY_HEIGHT), fill=GRASS_COLOR)

        # Place AI-generated art (Sun/Weather Icon)
        ai_art_size = int(DISPLAY_WIDTH * 0.3)
        ai_art_resized = ai_art.resize((ai_art_size, ai_art_size)) 
        img.paste(ai_art_resized, (30, 30)) 
        
        # Info Box
        box_x_start = 20
        box_y_start = int(DISPLAY_HEIGHT * 0.45) 
        box_width = DISPLAY_WIDTH - 40
        text_padding = 20
        box_height = DISPLAY_HEIGHT - box_y_start - 20

        draw.rectangle((box_x_start, box_y_start, box_x_start + box_width, box_y_start + box_height), fill='white', outline='black', width=3)

        # Location and Date Banner
        BANNER_COLOR = (255, 215, 0) 
        banner_y = box_y_start + 10
        banner_height = 50
        draw.rectangle((box_x_start + 5, banner_y, box_x_start + box_width - 5, banner_y + banner_height), fill=BANNER_COLOR)
        
        # Location Text
        loc_text = location.upper().split(',')[0].strip() # Use only city name
        loc_text_w = draw.textlength(loc_text, font=font_bold_large)
        draw.text((box_x_start + (box_width - loc_text_w)/2, box_y_start + 70), loc_text, fill='black', font=font_bold_large)
        
        # Date Text
        date_str = current_date.strftime("%A, %b %d")
        date_text_w = draw.textlength(date_str, font=font_bold_medium)
        draw.text((box_x_start + (box_width - date_text_w)/2, banner_y + (banner_height - draw.textlength("Test", font=font_bold_medium))/2 + 5), date_str, fill='black', font=font_bold_medium)

        # Weather Text
        weather_y = box_y_start + 150
        weather_text = f"{weather['icon']} {weather['condition']}: {weather['temp_str']}"
        draw.text((box_x_start + text_padding, weather_y), weather_text, fill='black', font=font_regular_small)
        
        # Separator Line
        line_y = weather_y + 40
        draw.line((box_x_start + text_padding, line_y, box_x_start + box_width - text_padding, line_y), fill='black', width=2)

        # Dad Joke
        joke_text = "Dad joke: " + dad_joke
        draw.text((box_x_start + text_padding, line_y + 15), joke_text, fill='black', font=font_regular_small)

        # 4. Return Image Bytes
        img_byte_arr = BytesIO()
        img.save(img_byte_arr, format='PNG') 
        
        return img_byte_arr.getvalue() 


# --- Flask Setup ---
app = Flask(__name__)
display_app = FamilyDisplayApp()

@app.route('/generate-display-image', methods=['GET'])
def get_display_image():
    """
    Receives only 'location' from the device.
    Example: /generate-display-image?location=Sydney,AU
    """
    # Get location from URL, default to Darwin, NT, Australia for the weather API
    location = request.args.get('location', 'Darwin, NT, AU')
    
    try:
        # 1. Fetch external data
        weather_data = display_app.fetch_weather_data(location)
        joke = display_app.fetch_dad_joke()
        
        # 2. Generate image
        image_bytes = display_app.generate_image(
            location=location,
            weather=weather_data,
            dad_joke=joke
        ) 
        
        return send_file(BytesIO(image_bytes), mimetype='image/png')
        
    except Exception as e:
        print(f"An unexpected error occurred in main route: {e}")
        # Return a simple error image
        error_img = Image.new('RGB', (200, 100), color='red')
        error_draw = ImageDraw.Draw(error_img)
        error_draw.text((10, 40), "SERVER ERROR", fill='white')
        error_bytes = BytesIO()
        error_img.save(error_bytes, format='PNG')
        return send_file(BytesIO(error_bytes.getvalue()), mimetype='image/png', status=500)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
