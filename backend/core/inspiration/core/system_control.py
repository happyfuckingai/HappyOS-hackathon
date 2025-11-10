"""
HappyOS System Control Layer
Provides UI automation, screen capture, and window management capabilities
"""
import os
import sys
import time
import subprocess
import logging
from typing import Optional, Tuple, List, Dict, Any
from pathlib import Path
import json
import base64
from io import BytesIO

# UI Automation imports
try:
    import pyautogui
    import cv2
    import numpy as np
    import pytesseract
    from PIL import Image, ImageGrab
    import psutil
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

logger = logging.getLogger(__name__)

class SystemControl:
    """Main system control class for UI automation and screen interaction"""

    def __init__(self, display: str = ":99"):
        self.display = display
        self.is_headless = os.environ.get('DISPLAY', '') == ''
        self.setup_environment()

    def setup_environment(self):
        """Set up the environment for UI automation"""
        os.environ['DISPLAY'] = self.display

        # Configure pyautogui for headless operation if needed
        if not self.is_headless and PYAUTOGUI_AVAILABLE:
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.1

        # Configure tesseract
        if not self.is_headless:
            try:
                pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
            except:
                logger.warning("Tesseract not found, OCR functionality will be limited")

    def take_screenshot(self, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[Image.Image]:
        """Take a screenshot of the entire screen or a specific region"""
        try:
            if self.is_headless:
                # Use scrot for headless screenshots
                screenshot_path = "/tmp/screenshot.png"
                cmd = ["scrot", screenshot_path]
                if region:
                    x, y, w, h = region
                    cmd = ["scrot", "-a", f"{x},{y},{w},{h}", screenshot_path]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0 and os.path.exists(screenshot_path):
                    screenshot = Image.open(screenshot_path)
                    os.remove(screenshot_path)
                    return screenshot
            else:
                # Use PIL ImageGrab for regular environments
                if region:
                    return ImageGrab.grab(bbox=region)
                else:
                    return ImageGrab.grab()

        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")

        return None

    def get_screen_size(self) -> Tuple[int, int]:
        """Get the current screen size"""
        try:
            if self.is_headless:
                # For headless, try to get from Xvfb
                result = subprocess.run(["xdpyinfo", "-display", self.display],
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'dimensions:' in line:
                            dims = line.split('dimensions:')[1].strip().split('pixels')[0].strip()
                            width, height = map(int, dims.split('x'))
                            return (width, height)
                return (1024, 768)  # Default Xvfb size
            else:
                return pyautogui.size()
        except Exception as e:
            logger.error(f"Failed to get screen size: {e}")
            return (1024, 768)

    def move_mouse(self, x: int, y: int, duration: float = 0.5):
        """Move mouse to specified coordinates"""
        try:
            if self.is_headless:
                subprocess.run(["xdotool", "mousemove", str(x), str(y)],
                             capture_output=True, timeout=5)
            else:
                pyautogui.moveTo(x, y, duration=duration)
        except Exception as e:
            logger.error(f"Failed to move mouse: {e}")

    def click_mouse(self, x: int, y: int, button: str = "left"):
        """Click mouse at specified coordinates"""
        try:
            if self.is_headless:
                button_map = {"left": "1", "middle": "2", "right": "3"}
                btn = button_map.get(button, "1")
                subprocess.run(["xdotool", "mousemove", str(x), str(y), "click", btn],
                             capture_output=True, timeout=5)
            else:
                pyautogui.click(x, y, button=button)
        except Exception as e:
            logger.error(f"Failed to click mouse: {e}")

    def type_text(self, text: str, interval: float = 0.1):
        """Type text using keyboard simulation"""
        try:
            if self.is_headless:
                subprocess.run(["xdotool", "type", "--delay", str(int(interval * 1000)), text],
                             capture_output=True, timeout=10)
            else:
                pyautogui.typewrite(text, interval=interval)
        except Exception as e:
            logger.error(f"Failed to type text: {e}")

    def press_key(self, key: str):
        """Press a keyboard key"""
        try:
            if self.is_headless:
                subprocess.run(["xdotool", "key", key],
                             capture_output=True, timeout=5)
            else:
                pyautogui.press(key)
        except Exception as e:
            logger.error(f"Failed to press key: {e}")

    def find_image_on_screen(self, template_path: str, confidence: float = 0.8) -> Optional[Tuple[int, int]]:
        """Find an image template on the screen using OpenCV"""
        try:
            screenshot = self.take_screenshot()
            if screenshot is None:
                return None

            # Convert PIL image to OpenCV format
            screen_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

            # Load template
            template = cv2.imread(template_path)
            if template is None:
                logger.error(f"Could not load template image: {template_path}")
                return None

            # Perform template matching
            result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val >= confidence:
                template_height, template_width = template.shape[:2]
                center_x = max_loc[0] + template_width // 2
                center_y = max_loc[1] + template_height // 2
                return (center_x, center_y)

        except Exception as e:
            logger.error(f"Failed to find image on screen: {e}")

        return None

    def extract_text_from_screen(self, region: Optional[Tuple[int, int, int, int]] = None, lang: str = 'eng') -> str:
        """Extract text from screen or region using OCR"""
        try:
            screenshot = self.take_screenshot(region)
            if screenshot is None:
                return ""

            # Convert PIL image to RGB if needed
            if screenshot.mode != 'RGB':
                screenshot = screenshot.convert('RGB')

            # Use pytesseract for OCR
            text = pytesseract.image_to_string(screenshot, lang=lang)
            return text.strip()

        except Exception as e:
            logger.error(f"Failed to extract text from screen: {e}")
            return ""

    def get_window_list(self) -> List[Dict[str, Any]]:
        """Get list of all windows"""
        try:
            if self.is_headless:
                result = subprocess.run(["wmctrl", "-l"],
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    windows = []
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            parts = line.split(None, 3)
                            if len(parts) >= 4:
                                window_id = parts[0]
                                desktop = parts[1]
                                client_machine = parts[2]
                                title = parts[3]
                                windows.append({
                                    "id": window_id,
                                    "desktop": desktop,
                                    "machine": client_machine,
                                    "title": title
                                })
                    return windows
            else:
                # Use pygetwindow if available
                try:
                    import pygetwindow
                    windows = []
                    for window in pygetwindow.getAllWindows():
                        windows.append({
                            "id": str(window._hWnd) if hasattr(window, '_hWnd') else window.title,
                            "title": window.title,
                            "left": window.left,
                            "top": window.top,
                            "width": window.width,
                            "height": window.height
                        })
                    return windows
                except ImportError:
                    pass

        except Exception as e:
            logger.error(f"Failed to get window list: {e}")

        return []

    def focus_window(self, window_id: str):
        """Focus a specific window"""
        try:
            if self.is_headless:
                subprocess.run(["wmctrl", "-i", "-a", window_id],
                             capture_output=True, timeout=5)
            else:
                try:
                    import pygetwindow
                    window = pygetwindow.getWindowsWithTitle(window_id)
                    if window:
                        window[0].activate()
                except ImportError:
                    pass
        except Exception as e:
            logger.error(f"Failed to focus window: {e}")

    def close_window(self, window_id: str):
        """Close a specific window"""
        try:
            if self.is_headless:
                subprocess.run(["wmctrl", "-i", "-c", window_id],
                             capture_output=True, timeout=5)
            else:
                try:
                    import pygetwindow
                    window = pygetwindow.getWindowsWithTitle(window_id)
                    if window:
                        window[0].close()
                except ImportError:
                    pass
        except Exception as e:
            logger.error(f"Failed to close window: {e}")

    def get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        try:
            info = {
                "screen_size": self.get_screen_size(),
                "is_headless": self.is_headless,
                "display": self.display,
                "cpu_count": psutil.cpu_count(),
                "memory": {
                    "total": psutil.virtual_memory().total,
                    "available": psutil.virtual_memory().available,
                    "used": psutil.virtual_memory().used
                },
                "disk": {
                    "total": psutil.disk_usage('/').total,
                    "free": psutil.disk_usage('/').free,
                    "used": psutil.disk_usage('/').used
                }
            }
            return info
        except Exception as e:
            logger.error(f"Failed to get system info: {e}")
            return {}

# Global system control instance
system_control = SystemControl()

# Convenience functions for easy access
def screenshot(region=None):
    """Take a screenshot"""
    return system_control.take_screenshot(region)

def mouse_move(x, y, duration=0.5):
    """Move mouse to coordinates"""
    system_control.move_mouse(x, y, duration)

def mouse_click(x, y, button="left"):
    """Click mouse at coordinates"""
    system_control.click_mouse(x, y, button)

def type_text(text, interval=0.1):
    """Type text"""
    system_control.type_text(text, interval)

def press_key(key):
    """Press a key"""
    system_control.press_key(key)

def find_image(template_path, confidence=0.8):
    """Find image on screen"""
    return system_control.find_image_on_screen(template_path, confidence)

def ocr_text(region=None, lang='eng'):
    """Extract text from screen"""
    return system_control.extract_text_from_screen(region, lang)

def get_windows():
    """Get window list"""
    return system_control.get_window_list()

def focus_window(window_id):
    """Focus window"""
    system_control.focus_window(window_id)

def close_window(window_id):
    """Close window"""
    system_control.close_window(window_id)

def get_system_info():
    """Get system info"""
    return system_control.get_system_info()