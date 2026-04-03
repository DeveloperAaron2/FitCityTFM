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
            "Eres un asistente de IA muy amistoso y comprensivo que valida levantamientos en un gimnasio aficionado. "
            f"A continuación, verás un montaje de 5 imágenes extraídas de un vídeo del usuario haciendo '{exercise_name}'.\n\n"
            "REGLA DE ORO DE ESTE GIMNASIO: Asume SIEMPRE que el levantamiento es VÁLIDO por defecto. Da por válido el levantamiento "
            "a menos que haya un fallo técnico gigantesco y catastrófico (ej: la barra se cae, no hace absolutamente ningún recorrido, "
            "el vídeo muestra otra persona u otro deporte distinto).\n\n"
        )
        
        name_lower = exercise_name.lower()
        if "sentadilla" in name_lower or "squat" in name_lower:
            rules = (
                "## Criterios SUPER permisivos para Sentadilla:\n"
                "1. Profundidad: Con que se note claramente que el usuario baja y vuelve a subir, DA EL LEVANTAMIENTO POR VÁLIDO.\n"
                "2. Si las imágenes no muestran bien el ángulo de la rodilla, asume que ha roto el paralelo y bájalo a válido.\n"
            )
        elif "banca" in name_lower or "bench" in name_lower:
            rules = (
                "## Criterios SUPER permisivos para Press de Banca:\n"
                "1. Con que la barra baje un poco hacia el pecho y vuelva a subir hacia arriba, DA EL LEVANTAMIENTO POR VÁLIDO.\n"
                "2. NO exijas pausas, ni que la barra toque obligatoriamente el pecho. NO exijas bloqueo de codos exacto.\n"
            )
        elif "muerto" in name_lower or "deadlift" in name_lower:
            rules = (
                "## Criterios SUPER permisivos para Peso Muerto:\n"
                "1. Si el usuario levanta la barra del suelo y más o menos termina de pie de nuevo con ella en las manos, DA EL LEVANTAMIENTO POR VÁLIDO.\n"
                "2. Ignora tirones irregulares, la curvatura de la espalda o rebotes.\n"
            )
        else:
            rules = (
                "## Criterios generales muy permisivos:\n"
                "Valida el movimiento siempre que se aprecie intención de esfuerzo y exista algo de recorrido aparente.\n"
            )
            
        json_instruct = (
            "\nIMPORTANTE: Como solo puedes ver 5 fotos estáticas sueltas del vídeo, lógicamente te estás perdiendo gran parte de la información fluida del movimiento y de los ángulos exactos. "
            "Por este motivo limitante de la tecnología, ante CUALQUIER mínima duda, debes priorizar siempre que la ejecución fue buena en los momentos que no viste y debes emitir un 'is_valid': true.\n\n"
            "Devuelve tu respuesta ÚNICAMENTE usando este modelo JSON exacto:\n"
            '{\n  "is_valid": true|false,\n  "reason": "<Breve mensaje de ánimo destacando que el levantamiento es válido (o un motivo muy claro y grave si fueras a darlo nulo)>",\n  "confidence": "high|medium|low"\n}'
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
