"""
URL Renderer Plugin for InkyPi

This plugin renders a web URL as a static image for the e-ink display.
"""

from plugins.base_plugin.base_plugin import BasePlugin
import logging
import subprocess
import tempfile
import os
from PIL import Image
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class URLRenderer(BasePlugin):

    def generate_image(self, settings, device_config):
        """Generates a static image from a URL."""
        url = settings.get('url')
        if not url:
            raise RuntimeError("URL not provided.")
        
        # Validate URL
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            # Add http:// prefix if missing
            if not parsed_url.scheme and parsed_url.path:
                url = f"https://{url}"
            else:
                raise RuntimeError("Invalid URL provided.")
        
        # Get device dimensions
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]
        
        # Optional zoom level setting
        zoom_level = settings.get('zoomLevel', '0.5')
        
        # Screenshot options
        options = {
            'zoom': zoom_level
        }
        
        try:
            image = self.take_webpage_screenshot(url, dimensions, options)
            if not image:
                raise RuntimeError("Failed to capture screenshot.")
            return image
        except Exception as e:
            logger.error(f"Failed to generate image from URL: {str(e)}")
            raise RuntimeError(f"Screenshot generation failed: {str(e)}")
    
    def take_webpage_screenshot(self, url, dimensions, options=None):
        """Takes a screenshot of a webpage using headless Chrome."""
        if options is None:
            options = {}
        
        base_width, base_height = dimensions
        zoom = float(options.get('zoom', '0.5'))  # Default to 50% zoom
        
        # Scale dimensions inversely to the zoom factor
        # For zoom 0.5 (50%), we want 2x the dimensions to show more content
        scaled_width = int(base_width / zoom)
        scaled_height = int(base_height / zoom)
        
        # Mobile user agent for better responsive display
        mobile_user_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
        
        image = None
        try:
            # Create a temporary output file for the screenshot
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as img_file:
                img_file_path = img_file.name
            
            # Build the command for taking a screenshot
            command = [
                "chromium-browser", url, "--headless=old",
                f"--screenshot={img_file_path}", 
                f"--window-size={scaled_width},{scaled_height}",
                f"--user-agent={mobile_user_agent}",
                "--no-sandbox", "--disable-gpu", 
                "--disable-software-rasterizer",
                "--disable-dev-shm-usage", "--hide-scrollbars"
            ]
            
            # Run the command
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            
            # Check if the process failed or the output file is missing
            if result.returncode != 0 or not os.path.exists(img_file_path):
                logger.error("Failed to take screenshot:")
                logger.error(result.stderr.decode('utf-8'))
                return None
            
            # Load the image using PIL
            image = Image.open(img_file_path)
            
            # Resize back to the original dimensions if zoom is not 1.0
            if zoom != 1.0:
                image = image.resize((base_width, base_height), Image.LANCZOS)
            
            # Cleanup temp file
            os.remove(img_file_path)
            
        except Exception as e:
            logger.error(f"Failed to take webpage screenshot: {str(e)}")
        
        return image