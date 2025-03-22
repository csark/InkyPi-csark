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
import requests
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
        
        # Optional additional settings
        zoom_level = settings.get('zoomLevel', '1.0')
        capture_full_page = settings.get('captureFullPage') == 'true'
        
        # Screenshot options
        options = {
            'zoom': zoom_level,
            'full_page': capture_full_page
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
        
        width, height = dimensions
        zoom = options.get('zoom', '1.0')
        full_page = options.get('full_page', False)
        
        image = None
        try:
            # Create a temporary output file for the screenshot
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as img_file:
                img_file_path = img_file.name
            
            # Build the command for taking a screenshot
            command = [
                "chromium-browser", url, "--headless=old",
                f"--screenshot={img_file_path}", 
                f"--window-size={width},{height}",
                "--no-sandbox", "--disable-gpu", 
                "--disable-software-rasterizer",
                "--disable-dev-shm-usage", "--hide-scrollbars",
                f"--force-device-scale-factor={zoom}"
            ]
            
            # Add full-page screenshot option if requested
            if full_page:
                command.append("--force-viewport-sizing")
            
            # Run the command
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            
            # Check if the process failed or the output file is missing
            if result.returncode != 0 or not os.path.exists(img_file_path):
                logger.error("Failed to take screenshot:")
                logger.error(result.stderr.decode('utf-8'))
                return None
            
            # Load the image using PIL
            image = Image.open(img_file_path)
            
            # For full page screenshots, we need to resize to fit the display
            if full_page:
                # Resize image while preserving aspect ratio
                image = self._resize_full_page(image, dimensions)
            
            # Cleanup temp file
            os.remove(img_file_path)
            
        except Exception as e:
            logger.error(f"Failed to take webpage screenshot: {str(e)}")
        
        return image
    
    def _resize_full_page(self, image, dimensions):
        """Resize a full-page screenshot to fit display dimensions."""
        img_width, img_height = image.size
        desired_width, desired_height = dimensions
        
        # Calculate ratios
        width_ratio = desired_width / img_width
        height_ratio = desired_height / img_height
        
        # Use the smaller ratio to ensure image fits within display
        ratio = min(width_ratio, height_ratio)
        
        # Calculate new dimensions
        new_width = int(img_width * ratio)
        new_height = int(img_height * ratio)
        
        # Resize the image
        return image.resize((new_width, new_height), Image.LANCZOS)