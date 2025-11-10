"""
Vision processor for Happy AI backend.
Handles processing of video frames and images.
"""

import os
import base64
import logging
import asyncio
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
# import io # Removed io

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

# Thread pool for CPU-intensive operations
executor = ThreadPoolExecutor(max_workers=2)

# Check if vision processing libraries are available
try:
    import cv2
    import numpy as np
    # from PIL import Image # Removed Image
    vision_processing_available = True
    logger.info("Vision processing libraries available")
except ImportError:
    vision_processing_available = False
    logger.warning("Vision processing libraries not installed")

async def process_image(image_base64: str) -> Dict[str, Any]:
    """
    Processes an image from base64 data.
    
    Args:
        image_base64: Base64-encoded image data
        
    Returns:
        Dictionary with processing results
    """
    if not vision_processing_available:
        logger.error("Vision processing not available")
        return {"error": "Vision processing not available"}
    
    try:
        # Convert base64 to image data
        image_data = base64.b64decode(image_base64)
        
        # Process image in a separate thread
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            lambda: _process_image_data(image_data)
        )
        
        logger.info("Image processing successful")
        return result
    
    except Exception as e:
        logger.error(f"Error in image processing: {e}")
        return {"error": str(e)}

def _process_image_data(image_data: bytes) -> Dict[str, Any]:
    """
    Processes image data (runs in a separate thread).
    
    Args:
        image_data: The image data
        
    Returns:
        Dictionary with processing results
    """
    # Convert bytes to numpy array
    nparr = np.frombuffer(image_data, np.uint8)
    
    # Decode image
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # Basic image analysis
    height, width, channels = img.shape
    
    # Convert to grayscale for face detection
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Load face cascade (if available)
    face_cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    
    if os.path.exists(face_cascade_path):
        face_cascade = cv2.CascadeClassifier(face_cascade_path)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        # Process detected faces
        face_data = []
        for (x, y, w, h) in faces:
            face_data.append({
                "x": int(x),
                "y": int(y),
                "width": int(w),
                "height": int(h)
            })
    else:
        face_data = []
        logger.warning("Face cascade file not found")
    
    # Return processing results
    return {
        "dimensions": {
            "width": width,
            "height": height,
            "channels": channels
        },
        "faces_detected": len(face_data),
        "faces": face_data,
        "timestamp": asyncio.get_event_loop().time()
    }

async def generate_image_description(image_base64: str) -> Optional[str]:
    """
    Generates a description of an image using AI.
    
    Uses the available LLM client to generate image descriptions.
    Falls back to basic analysis if vision models are not available.
    
    Args:
        image_base64: Base64-encoded image data
        
    Returns:
        Description of the image, or None if generation failed
    """
    try:
        from app.llm.router import get_llm_client
        
        # Get the LLM client
        llm_client = get_llm_client()
        if not llm_client:
            logger.warning("No LLM client available for image description")
            return await _generate_basic_description(image_base64)
        
        # Check if the client supports vision
        if hasattr(llm_client, 'supports_vision') and llm_client.supports_vision:
            # Use vision-capable model
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Beskriv denna bild på svenska. Var detaljerad och inkludera vad du ser, färger, objekt, personer och aktiviteter."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ]
            
            response = await llm_client.generate(messages, model="gpt-4-vision-preview")
            description = response.get("content", "").strip()
            
            if description:
                logger.info("Generated AI image description successfully")
                return description
        
        # Fallback to basic description if vision not supported
        return await _generate_basic_description(image_base64)
        
    except Exception as e:
        logger.error(f"Error generating image description: {e}")
        return await _generate_basic_description(image_base64)


async def _generate_basic_description(image_base64: str) -> str:
    """
    Generates a basic description based on image analysis.
    
    Args:
        image_base64: Base64-encoded image data
        
    Returns:
        Basic description of the image
    """
    try:
        # Process the image to get basic information
        analysis = await process_image(image_base64)
        
        if "error" in analysis:
            return "Kunde inte analysera bilden."
        
        # Build description from analysis
        dimensions = analysis.get("dimensions", {})
        faces_count = analysis.get("faces_detected", 0)
        
        description_parts = []
        
        # Add dimension info
        if dimensions:
            width = dimensions.get("width", 0)
            height = dimensions.get("height", 0)
            description_parts.append(f"Bild med dimensioner {width}x{height} pixlar")
        
        # Add face detection info
        if faces_count > 0:
            if faces_count == 1:
                description_parts.append("Ett ansikte upptäckt")
            else:
                description_parts.append(f"{faces_count} ansikten upptäckta")
        else:
            description_parts.append("Inga ansikten upptäckta")
        
        # Combine description
        if description_parts:
            return ". ".join(description_parts) + "."
        else:
            return "Grundläggande bildanalys genomförd."
            
    except Exception as e:
        logger.error(f"Error in basic image description: {e}")
        return "Kunde inte generera bildbeskrivning."