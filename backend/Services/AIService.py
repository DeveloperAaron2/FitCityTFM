import os
import httpx
import base64
import tempfile
import cv2  # requires opencv-python-headless
import json
from typing import Dict, Any

# Environment variables for Ollama (so it can be pointing to Ollama Cloud later)
# Assuming a multimodal model like llava or llama3.2-vision
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llava:13b")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")

class AIService:
    def __init__(self):
        self.base_url = OLLAMA_BASE_URL.rstrip('/')
        self.model = OLLAMA_MODEL
        self.headers = {}
        if OLLAMA_API_KEY:
            self.headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"

    async def analyze_lifting_video(self, video_bytes: bytes, exercise_name: str) -> Dict[str, Any]:
        """
        Extracts frames from the video and sends them to Ollama for analysis
        based on the Spanish Powerlifting (AEP/IPF) rules.
        """
        try:
            # 1. Extract frames from video as Base64 strings
            base64_frames = self._extract_frames(video_bytes, num_frames=5)
            
            if not base64_frames:
                return {
                    "is_valid": False, 
                    "reason": "No se pudo procesar el vídeo o no contiene suficientes frames.", 
                    "confidence": "high"
                }

            # 2. Build the prompt according to the AEP/IPF rules
            prompt = self._build_prompt(exercise_name)
            
            # 3. Call Ollama API
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        f"{self.base_url}/api/generate",
                        headers=self.headers,
                        json={
                            "model": self.model,
                            "prompt": prompt,
                            "images": base64_frames,
                            "stream": False,
                            "format": "json" # Force JSON output from the model
                        },
                        timeout=180.0
                    )
                    response.raise_for_status()
                    result = response.json()
                except httpx.HTTPStatusError as exc:
                    err_msg = exc.response.text
                    return {
                        "is_valid": False,
                        "reason": f"Ollama rechazó la petición ({exc.response.status_code}): El modelo '{self.model}' podría no estar descargado.",
                        "confidence": "low",
                        "debug_info": err_msg
                    }
                except httpx.RequestError as exc:
                    return {
                        "is_valid": False,
                        "reason": f"No se pudo conectar con Ollama en {self.base_url}. Asegúrate de que está ejecutándose.",
                        "confidence": "low"
                    }
                
                # Parse model answer
                llm_text = result.get("response", "{}")
                try:
                    data = json.loads(llm_text)
                    return {
                        "is_valid": data.get("is_valid", False),
                        "reason": data.get("reason", llm_text),
                        "confidence": data.get("confidence", "low")
                    }
                except json.JSONDecodeError:
                    return {
                        "is_valid": False,
                        "reason": f"Respuesta no válida del modelo: {llm_text}",
                        "confidence": "low"
                    }
        except Exception as e:
            return {
                "is_valid": False,
                "reason": f"Error interno en el análisis del servidor de IA: {str(e)}",
                "confidence": "low"
            }

    def _build_prompt(self, exercise_name: str) -> str:
        base_prompt = (
            "Eres un árbitro profesional estricto de Powerlifting de la AEP (Asociación Española de Powerlifting) e IPF. "
            "Se te proporcionará una secuencia temporal de 5 imágenes (frames) extraídas de un vídeo que muestran la "
            f"ejecución de un usuario realizando el levantamiento de '{exercise_name}'.\n\n"
        )
        
        name_lower = exercise_name.lower()
        if "sentadilla" in name_lower or "squat" in name_lower:
            rules = (
                "## Normativa Oficial de Sentadilla (Squat):\n"
                "1. Profundidad: El pliegue de la cadera (la parte superior del muslo en la articulación de la cadera) "
                "debe descender notablemente por debajo del nivel de la parte superior de las rodillas ('romper el paralelo').\n"
                
            )
        elif "banca" in name_lower or "bench" in name_lower:
            rules = (
                "## Normativa Oficial de Press de Banca (Bench Press):\n"
                "1. Contacto: La barra debe descender hasta tocar el pecho (o el área abdominal) y hacer una visible pausa perdiendo "
                "inercia antes del empuje concéntrico.\n"
                "2. Posición: La cabeza, hombros y nalgas deben estar en contacto con el banco en todo momento. "
                "Ambos pies deben estar apoyados planos sobre el suelo o bloques.\n"
                "3. Extensión: Al finalizar el movimiento, los brazos deben lograr una extensión simultánea "
                "y un bloqueo completo de los codos.\n"
            )
        elif "muerto" in name_lower or "deadlift" in name_lower:
            rules = (
                "## Normativa Oficial de Peso Muerto (Deadlift):\n"
                "1. Hitching: No se permite apoyar la barra sobre los muslos durante el levantamiento "
                "para utilizar los muslos como apoyo antes de lograr el bloqueo.\n"
                "2. Movimiento: No está permitido cualquier movimiento descendente de la barra antes de alcanzar el bloqueo final.\n"
                "3. Bloqueo: En el final del movimiento, las rodillas deben estar rectas y los hombros hacia atrás "
                "(posición erguida completa).\n"
            )
        else:
            rules = (
                "## Criterios de evaluación técnica:\n"
                "Evalúa de la forma más estricta si el rango de movimiento es completo, si la ejecución es "
                "biomecánicamente segura, controlada y sin inercias innecesarias.\n"
            )
            
        json_instruct = (
            "\nTU TRABAJO:\n"
            "Examina las 5 imágenes proporcionadas buscando infracciones a la normativa mencionada.\n"
            "Devuelve tu respuesta estricta y ÚNICAMENTE en este esquema de JSON válido en español:\n"
            '{\n  "is_valid": true|false,\n  "reason": "<Breve explicación arbitral (1 frase) justificando el nulo o válido>",\n  "confidence": "high|medium|low"\n}'
        )
        
        return base_prompt + rules + json_instruct
        
    def _extract_frames(self, video_bytes: bytes, num_frames: int = 5) -> list[str]:
        """
        Extrae `num_frames` imágenes equidistantes de un buffer de vídeo en memoria para su análisis multi-modal.
        """
        # Save bytes to a temp file because cv2 needs a file path
        fd, tmp_path = tempfile.mkstemp(suffix=".mp4")
        with os.fdopen(fd, 'wb') as f:
            f.write(video_bytes)
            
        frames_b64 = []
        try:
            cap = cv2.VideoCapture(tmp_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if total_frames <= 0:
                print("Warning (AIService): No se pudo leer el número de frames.")
                return frames_b64
                
            # Get 5 evenly spaced frames avoiding the exact first and last if possible to skip blanking
            step = max(total_frames // (num_frames + 1), 1)
            
            for i in range(1, num_frames + 1):
                frame_idx = min(i * step, total_frames - 1)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                
                if ret:
                    # Resize to reduce payload for Ollama Cloud/Local
                    # Keep aspect ratio, scale height to ~512
                    h, w = frame.shape[:2]
                    new_h = 512
                    new_w = int(w * (new_h / h))
                    resized = cv2.resize(frame, (new_w, new_h))
                    
                    # Encode as JPEG buffer
                    success, buffer = cv2.imencode('.jpg', resized)
                    if success:
                        b64_str = base64.b64encode(buffer).decode('utf-8')
                        frames_b64.append(b64_str)
                        
            cap.release()
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
        return frames_b64

# Instantiate to use in FastAPI endpoints
ai_service = AIService()
