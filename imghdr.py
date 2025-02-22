# imghdr.py
from PIL import Image

def what(filename, h=None):
    """
    Open an image file using Pillow and return a string representing its format.
    If the image cannot be opened or its format is not recognized, return None.
    """
    try:
        with Image.open(filename) as img:
            fmt = img.format.lower()
            # Map 'jpeg' as needed (Pillow returns 'jpeg' for JPEG images)
            return fmt
    except Exception as e:
        print(f"imghdr error: {e}")
        return None

# Optionally, you can define a tests dictionary if needed by consumers.
tests = {}
