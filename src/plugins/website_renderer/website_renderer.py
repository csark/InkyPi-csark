from plugins.base_plugin.base_plugin import BasePlugin
from PIL import Image, ImageEnhance
import logging
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class WebsiteRenderer(BasePlugin):
    def generate_image(self, settings, device_config):
        url = settings.get('website_url', 'https://example.com')
        settings['content_scale'] = int(settings.get('content_scale', 100))
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        width, height = device_config.get_resolution()
        
        try:
            # Fetch the website content
            response = requests.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1'
            })
            html_content = response.text
            
            # Process the HTML for color e-ink display
            processed_html = self._process_html(html_content, url, settings)
            
            # Add current datetime for the footer
            current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            # Render using the built-in HTML renderer
            return self.render_image(
                (width, height),
                "webpage_wrapper.html",
                "webpage_style.css",
                {
                    "processed_html": processed_html, 
                    "url": url,
                    "current_datetime": current_datetime,
                    "plugin_settings": settings
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to render website: {e}")
            return self._generate_error_image(width, height, str(e))
    
    def _process_html(self, html_content, base_url, settings):
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove elements that don't render well on e-ink
        for element in soup.select('video, iframe, script, noscript, svg'):
            element.decompose()
        
        # Preserve stylesheets but remove @import and web fonts for performance
        for style in soup.find_all('style'):
            if style.string:
                # Remove @import rules and web fonts which can slow rendering
                style.string = re.sub(r'@import.*?;', '', style.string)
                style.string = re.sub(r'@font-face.*?}', '', style.string)
        
        # Optimize images for color e-ink
        saturation_level = int(settings.get('color_saturation', 120))
        for img in soup.find_all('img'):
            if img.get('src'):
                # Convert relative URLs to absolute
                if not img['src'].startswith(('http://', 'https://', 'data:')):
                    img['src'] = self._make_absolute_url(img['src'], base_url)
                
                # Add a color optimization class
                img['class'] = img.get('class', []) + ['eink-optimized-image']
                img['style'] = f'filter: saturate({saturation_level}%) contrast(110%);'
        
        # Fix relative links
        for a in soup.find_all('a', href=True):
            if not a['href'].startswith(('http://', 'https://', '#', 'mailto:', 'tel:')):
                a['href'] = self._make_absolute_url(a['href'], base_url)
        
        # Add color optimization styles
        color_style = soup.new_tag('style')
        color_style.string = self._generate_color_optimization_css(settings)
        soup.head.append(color_style)
        
        # Extract only the main content area if reader mode is enabled
        if settings.get('reader_mode', False):
            main_content = self._extract_main_content(soup)
            if main_content:
                # Create a simplified document with just the main content
                new_soup = BeautifulSoup('<div id="main-content"></div>', 'html.parser')
                new_soup.find(id="main-content").append(main_content)
                soup = new_soup
        
        return str(soup)
    
    def _generate_color_optimization_css(self, settings):
        """Generate CSS to optimize colors for e-ink display"""
        saturation = int(settings.get('color_saturation', 120))
        contrast = int(settings.get('contrast', 110))
        
        return f"""
        /* E-ink color optimization */
        body {{
            filter: saturate({saturation}%) contrast({contrast}%);
        }}
        """
    
    def _make_absolute_url(self, relative_url, base_url):
        """Convert a relative URL to an absolute URL"""
        from urllib.parse import urljoin
        return urljoin(base_url, relative_url)
    
    def _extract_main_content(self, soup):
        """Extract the main content area using heuristics"""
        # Look for common content container IDs and classes
        content_selectors = [
            'article', 'main', '.content', '#content', '.post', '.article',
            '[role="main"]', '.main-content', '#main-content'
        ]
        
        for selector in content_selectors:
            content = soup.select_one(selector)
            if content and len(str(content)) > 500:  # Require a minimum length
                return content
        
        # If no suitable content container is found, return the whole body
        return soup.body
        
    def _generate_error_image(self, width, height, error_message):
        """Generate an error image with the error message"""
        return self.render_image(
            (width, height),
            "error.html",
            None,
            {"error_message": error_message}
        )