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
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llava")
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
            base64_frames = self._extract_frames(video_bytes, num_frames=8)
            
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
                        timeout=900.0 # Ampliado a 15 min para evitar cortes al usar CPU puro
                    )
                    response.raise_for_status()
                    result = response.json()
                except httpx.HTTPStatusError as exc:
                    err_msg = exc.response.text
                    return {
                        "is_valid": False,
                        "reason": f"Ollama rechazó la petición ({exc.response.status_code}): El modelo '{self.model}' podría no estar descargado o colapsó.",
                        "confidence": "low",
                        "debug_info": err_msg
                    }
                except httpx.TimeoutException:
                    return {
                        "is_valid": False,
                        "reason": "El análisis ha tardado demasiado (Timeout). La IA está procesando por CPU las 8 imágenes y requiere más tiempo.",
                        "confidence": "low"
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

    async def estimate_weight_from_video(
        self, video_bytes: bytes, exercise_name: str, declared_weight: float
    ) -> dict:
        """
        Extracts frames from the video and asks the model to estimate
        the total weight on the barbell by identifying visible plates.
        Returns a comparison against the declared weight.
        """
        try:
            base64_frames = self._extract_frames(video_bytes, num_frames=3)

            if not base64_frames:
                return {
                    "estimated_weight": None,
                    "matches_declared": True,
                    "confidence": "none",
                    "detail": "No se pudieron extraer frames para estimar el peso.",
                }

            prompt = self._build_weight_estimation_prompt(exercise_name, declared_weight)

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
                            "format": "json",
                        },
                        timeout=600.0,
                    )
                    response.raise_for_status()
                    result = response.json()
                except httpx.TimeoutException:
                    return {
                        "estimated_weight": None,
                        "matches_declared": True,
                        "confidence": "none",
                        "detail": "El servicio de IA ha tardado demasiado en estimar el peso (Timeout intentando procesar por CPU).",
                    }
                except (httpx.HTTPStatusError, httpx.RequestError):
                    return {
                        "estimated_weight": None,
                        "matches_declared": True,
                        "confidence": "none",
                        "detail": "No se pudo conectar con el servicio de IA para estimar el peso.",
                    }

                llm_text = result.get("response", "{}")
                try:
                    data = json.loads(llm_text)
                    estimated = data.get("estimated_weight_kg")
                    if estimated is not None:
                        try:
                            estimated = float(estimated)
                        except (ValueError, TypeError):
                            estimated = None

                    # Compare: allow a tolerance of ±20% between estimated and declared
                    if estimated is not None and estimated > 0:
                        tolerance = 0.20
                        lower = estimated * (1 - tolerance)
                        upper = estimated * (1 + tolerance)
                        matches = lower <= declared_weight <= upper
                    else:
                        matches = True  # Can't estimate → assume OK

                    return {
                        "estimated_weight": estimated,
                        "matches_declared": matches,
                        "confidence": data.get("confidence", "low"),
                        "detail": data.get("detail", ""),
                    }
                except json.JSONDecodeError:
                    return {
                        "estimated_weight": None,
                        "matches_declared": True,
                        "confidence": "none",
                        "detail": "Respuesta no válida del modelo al estimar peso.",
                    }
        except Exception as e:
            return {
                "estimated_weight": None,
                "matches_declared": True,
                "confidence": "none",
                "detail": f"Error interno al estimar peso: {str(e)}",
            }

    def _build_weight_estimation_prompt(
        self, exercise_name: str, declared_weight: float
    ) -> str:
        return (
            "Eres un asistente de IA experto en identificar discos de pesas en imágenes de gimnasio. "
            f"El usuario dice que está levantando {declared_weight} kg en '{exercise_name}'.\n\n"
            "Analiza las imágenes e intenta estimar el peso total en la barra contando los discos visibles.\n\n"
            "REFERENCIA DE DISCOS CALIBRADOS (colores IPF estándar):\n"
            "- Rojo = 25 kg\n"
            "- Azul = 20 kg\n"
            "- Amarillo = 15 kg\n"
            "- Verde = 10 kg\n"
            "- Blanco = 5 kg\n"
            "- Discos pequeños: 2.5 kg, 1.25 kg\n"
            "- La barra olímpica pesa 20 kg normalmente\n\n"
            "NOTA: Los discos se cargan a ambos lados de la barra (simétricos). "
            "Si ves discos solo en un lado, multiplica por 2.\n\n"
            "Si NO puedes ver los discos con claridad (ángulo malo, discos negros sin marcar, "
            "mala iluminación), indica confidence 'low' y estimated_weight_kg como null.\n\n"
            "Devuelve ÚNICAMENTE este JSON:\n"
            '{\n'
            '  "estimated_weight_kg": <número o null si no es posible estimar>,\n'
            '  "confidence": "high|medium|low",\n'
            '  "detail": "<breve explicación de qué discos has identificado o por qué no puedes estimar>"\n'
            '}'
        )

    def _build_prompt(self, exercise_name: str) -> str:
        base_prompt = (
            "Eres un árbitro de powerlifting que valida levantamientos aplicando las reglas de la AEP/IPF. "
            f"Vas a ver 8 fotogramas extraídos de un vídeo del usuario realizando '{exercise_name}'.\n\n"
            "PASO 1 — VERIFICACIÓN DEL EJERCICIO:\n"
            f"Comprueba que el movimiento que aparece en las imágenes ES realmente '{exercise_name}'. "
            "Si el vídeo muestra claramente un ejercicio completamente distinto (ej: se pide sentadilla pero se ve press de banca), "
            "devuelve is_valid: false indicando que el ejercicio no corresponde. "
            "Si hay duda razonable o el ángulo es ambiguo, continúa con la evaluación.\n\n"
            "PASO 2 — EVALUACIÓN TÉCNICA:\n"
            "Evalúa la técnica con los criterios específicos del ejercicio (ver abajo). "
            "No asumas válido por defecto: emite is_valid: true solo si los criterios principales se cumplen "
            "o si la imagen no permite determinar el fallo con certeza.\n\n"
        )

        name_lower = exercise_name.lower()
        if "sentadilla" in name_lower or "squat" in name_lower:
            rules = (
                "## Criterios para Sentadilla (AEP/IPF simplificado):\n"
                "VÁLIDO si se cumplen los 3 puntos:\n"
                "1. PROFUNDIDAD: Se aprecia que la cadera desciende hasta quedar al nivel o por debajo de la línea superior de las rodillas "
                "(plano del muslo paralelo o más bajo). Si el ángulo no permite ver la profundidad, beneficio de la duda → válido.\n"
                "2. RECORRIDO COMPLETO: El atleta arranca de pie, desciende y regresa a posición erguida con rodillas extendidas.\n"
                "3. BARRA EN POSICIÓN: La barra está sobre los hombros/trapecios (no en el cuello ni en las manos sueltas).\n"
                "INVÁLIDO solo si se aprecia claramente que la cadera queda muy por encima de las rodillas (sin profundidad evidente) "
                "o el atleta no llega a ponerse de pie al finalizar.\n"
            )
        elif "banca" in name_lower or "bench" in name_lower:
            rules = (
                "## Criterios para Press de Banca (AEP/IPF simplificado):\n"
                "VÁLIDO si se cumplen los 3 puntos:\n"
                "1. TOQUE AL PECHO: La barra desciende hasta contactar o casi contactar el pecho/esternón del atleta. "
                "Si la barra se acerca claramente al pecho pero el fotograma no muestra el contacto exacto, beneficio de la duda → válido.\n"
                "2. EXTENSIÓN FINAL: La barra sube hasta que los codos quedan visiblemente extendidos al final del movimiento.\n"
                "3. POSICIÓN EN EL BANCO: El atleta está tumbado boca arriba sobre el banco durante todo el levantamiento.\n"
                "INVÁLIDO solo si se ve claramente que la barra no baja más allá de la mitad del recorrido "
                "o el atleta se levanta del banco de forma evidente.\n"
            )
        elif "muerto" in name_lower or "deadlift" in name_lower:
            rules = (
                "## Criterios para Peso Muerto (AEP/IPF simplificado):\n"
                "VÁLIDO si se cumplen los 3 puntos:\n"
                "1. DESPEGUE DEL SUELO: La barra parte claramente desde el suelo (o muy cerca) al inicio del levantamiento.\n"
                "2. LOCKOUT FINAL: El atleta termina erguido con caderas y rodillas extendidas y hombros por detrás de la vertical de la barra. "
                "Si el fotograma final muestra al atleta de pie sosteniendo la barra, es suficiente.\n"
                "3. CONTROL DE LA BARRA: La barra no se suelta ni cae de forma incontrolada durante el levantamiento.\n"
                "INVÁLIDO solo si la barra claramente no despega del suelo "
                "o el atleta no llega a ninguna posición erguida al finalizar.\n"
            )
        else:
            rules = (
                "## Criterios generales de levantamiento:\n"
                "VÁLIDO si: el atleta realiza un recorrido de movimiento completo y controlado con la carga, "
                "comenzando y terminando en una posición estable.\n"
                "INVÁLIDO solo si: no hay recorrido apreciable, la carga cae de forma incontrolada "
                "o el movimiento no guarda ninguna relación con el ejercicio declarado.\n"
            )

        json_instruct = (
            "\nNOTA TÉCNICA: Dispones de 8 fotogramas distribuidos entre el 10% y el 90% del vídeo para cubrir la fase activa del levantamiento. "
            "Si un criterio no puede evaluarse con certeza por el ángulo o la calidad de imagen, aplica beneficio de la duda para ese criterio concreto.\n\n"
            "Devuelve tu respuesta ÚNICAMENTE con este JSON exacto (sin texto adicional):\n"
            '{\n'
            '  "is_valid": true|false,\n'
            '  "reason": "<Explica brevemente qué criterios se cumplen o cuál falla de forma clara>",\n'
            '  "confidence": "high|medium|low"\n'
            '}'
        )

        return base_prompt + rules + json_instruct
        
    def _extract_frames(self, video_bytes: bytes, num_frames: int = 8) -> list[str]:
        """
        Extrae `num_frames` imágenes del buffer de vídeo cubriendo del 10% al 90% del metraje
        para capturar la fase activa del levantamiento y evitar frames en negro del inicio/fin.
        """
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

            # Distribute frames between 10% and 90% of the video to cover the active lift phase
            step = max((total_frames * 0.8) // num_frames, 1)
            start_frame = int(total_frames * 0.1)

            for i in range(num_frames):
                frame_idx = int(start_frame + min(i * step, int(total_frames * 0.9) - start_frame))
                frame_idx = min(frame_idx, total_frames - 1)
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()

                if ret:
                    h, w = frame.shape[:2]
                    new_h = 512
                    new_w = int(w * (new_h / h))
                    resized = cv2.resize(frame, (new_w, new_h))

                    success, buffer = cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
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
