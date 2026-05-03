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
        Extracts frames from the video and sends them to Ollama for analysis.
        Validates safety and minimum range of motion for standard gym users.
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

            # 2. Build the prompt for the exercise
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
                            "format": "json"  # Force JSON output from the model
                        },
                        timeout=900.0  # Ampliado a 15 min para evitar cortes al usar CPU puro
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

                    confidence = data.get("confidence", "low")

                    # Only flag a mismatch when the model is confident enough to count plates.
                    # With low confidence the estimate is too unreliable to penalise the user.
                    if estimated is not None and estimated > 0 and confidence in ("high", "medium"):
                        # ±15% tolerance to absorb small plate-counting errors
                        tolerance = 0.15
                        lower = estimated * (1 - tolerance)
                        upper = estimated * (1 + tolerance)
                        matches = lower <= declared_weight <= upper
                    else:
                        matches = True  # Can't estimate reliably → assume OK

                    return {
                        "estimated_weight": estimated,
                        "matches_declared": matches,
                        "confidence": confidence,
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
        # NOTE: declared_weight is intentionally NOT included in the prompt to avoid
        # anchoring the model towards confirming whatever the user declared.
        return (
            f"Eres un asistente experto en identificar equipamiento de gimnasio. "
            f"El usuario está realizando '{exercise_name}'. "
            "Analiza las imágenes y estima el peso total cargado en la barra "
            "contando los discos que puedas ver.\n\n"
            "CÓMO CALCULAR EL PESO TOTAL:\n"
            "1. Identifica el tipo de barra: olímpica estándar = 20 kg, barra corta/EZ = ~10 kg.\n"
            "2. Cuenta los discos visibles en UN lado de la barra y multiplica por 2 "
            "(los discos siempre se cargan simétricamente en ambos lados).\n"
            "3. Suma: peso barra + (discos un lado × 2) = peso total.\n\n"
            "REFERENCIA DE DISCOS (colores más habituales en gimnasios):\n"
            "- Rojo = 25 kg | Azul = 20 kg | Amarillo = 15 kg | Verde = 10 kg | Blanco = 5 kg\n"
            "- Discos negros de goma: busca el número grabado o impreso en el disco para identificar el peso.\n"
            "- Discos pequeños: 2.5 kg, 1.25 kg (normalmente metálicos o con marcas visibles).\n\n"
            "NIVELES DE CONFIANZA — elige el que corresponda:\n"
            "- 'high': ves los discos con claridad, puedes leer o identificar el peso de cada uno.\n"
            "- 'medium': ves la mayoría de los discos pero alguno es dudoso o está parcialmente tapado.\n"
            "- 'low': los discos no son visibles, están fuera de plano, son negros sin marcas legibles "
            "o la iluminación impide identificarlos.\n\n"
            "IMPORTANTE: Si la confianza es 'low', devuelve estimated_weight_kg como null. "
            "No inventes un número si no puedes contarlos con cierta seguridad.\n\n"
            "Devuelve ÚNICAMENTE este JSON (sin texto adicional):\n"
            '{\n'
            '  "estimated_weight_kg": <número con hasta 1 decimal, o null>,\n'
            '  "confidence": "high|medium|low",\n'
            '  "detail": "<describe brevemente los discos identificados o el motivo por el que no puedes estimar>"\n'
            '}'
        )

    def _build_prompt(self, exercise_name: str) -> str:
        base_prompt = (
            "Eres un asistente de registro deportivo en una app de gimnasio. "
            f"Vas a ver 8 fotogramas de un vídeo del usuario realizando '{exercise_name}'.\n\n"
            "TU ÚNICO OBJETIVO es detectar si el movimiento se ha ejecutado o no. "
            "No eres un árbitro ni un entrenador: no penalices la técnica imperfecta. "
            "La inmensa mayoría de los levantamientos deben resultar VÁLIDOS.\n\n"
            "REGLA DE ORO: ante cualquier duda, ángulo no ideal, técnica imperfecta "
            "o imposibilidad de determinar algo con certeza → is_valid: true. "
            "Solo marca is_valid: false ante evidencia clara e inequívoca de los casos INVÁLIDO de abajo.\n\n"
        )

        name_lower = exercise_name.lower()
        if "sentadilla" in name_lower or "squat" in name_lower:
            rules = (
                "## Sentadilla — INVÁLIDO únicamente si ocurre alguno de estos casos evidentes:\n"
                "- El usuario no dobla las rodillas en absoluto (permanece totalmente erguido sin ningún descenso).\n"
                "- El usuario cae o pierde la barra de forma completamente incontrolada.\n"
                "- El vídeo muestra inequívocamente un ejercicio distinto a una sentadilla.\n"
                "VÁLIDO todo lo demás: poca profundidad, rodillas ligeramente hacia dentro, "
                "espalda inclinada, subida lenta, cualquier variante (frontal, sumo, goblet…).\n"
            )
        elif "banca" in name_lower or "bench" in name_lower:
            rules = (
                "## Press de Banca — INVÁLIDO únicamente si ocurre alguno de estos casos evidentes:\n"
                "- Los brazos no bajan en absoluto desde la posición inicial (recorrido completamente nulo).\n"
                "- La barra cae sobre el pecho de forma completamente incontrolada.\n"
                "- El vídeo muestra inequívocamente un ejercicio distinto a un press de banca.\n"
                "VÁLIDO todo lo demás: que no toque el pecho, codos no del todo extendidos, "
                "agarre ancho o estrecho, ligero rebote, arqueo de espalda.\n"
            )
        elif "muerto" in name_lower or "deadlift" in name_lower:
            rules = (
                "## Peso Muerto — INVÁLIDO únicamente si ocurre alguno de estos casos evidentes:\n"
                "- La barra no se despega del suelo en absoluto (el usuario tira pero no sube nada).\n"
                "- La barra se suelta y cae de forma completamente incontrolada a mitad del movimiento.\n"
                "- El vídeo muestra inequívocamente un ejercicio distinto a un peso muerto.\n"
                "VÁLIDO todo lo demás: espalda redondeada, lockout incompleto, rebote, "
                "piernas muy dobladas, cualquier variante (sumo, rumano, trap bar…).\n"
            )
        else:
            rules = (
                "## Ejercicio general — INVÁLIDO únicamente si ocurre alguno de estos casos evidentes:\n"
                "- No hay ningún movimiento apreciable con la carga (recorrido absolutamente nulo).\n"
                "- La carga cae de forma completamente incontrolada causando un incidente claro.\n"
                "- El vídeo muestra inequívocamente un ejercicio totalmente diferente al declarado.\n"
                "VÁLIDO todo lo demás.\n"
            )

        json_instruct = (
            "\nNOTA: Tienes 8 fotogramas estáticos del 10% al 90% del vídeo; "
            "no muestran el movimiento completo. Ante cualquier duda → is_valid: true.\n\n"
            "Devuelve ÚNICAMENTE este JSON exacto (sin texto adicional):\n"
            '{\n'
            '  "is_valid": true|false,\n'
            '  "reason": "<Una frase: confirma que el movimiento se ha realizado, '
            'o indica el fallo concreto e inequívoco detectado>",\n'
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
