<<<<<<< HEAD
# FitcityFrontend

This project was generated using [Angular CLI](https://github.com/angular/angular-cli) version 19.2.21.

## Development server

To start a local development server, run:

```bash
ng serve
```

Once the server is running, open your browser and navigate to `http://localhost:4200/`. The application will automatically reload whenever you modify any of the source files.

## Code scaffolding

Angular CLI includes powerful code scaffolding tools. To generate a new component, run:

```bash
ng generate component component-name
```

For a complete list of available schematics (such as `components`, `directives`, or `pipes`), run:

```bash
ng generate --help
```

## Building

To build the project run:

```bash
ng build
```

This will compile your project and store the build artifacts in the `dist/` directory. By default, the production build optimizes your application for performance and speed.

## Running unit tests

To execute unit tests with the [Karma](https://karma-runner.github.io) test runner, use the following command:

```bash
ng test
```

## Running end-to-end tests

For end-to-end (e2e) testing, run:

```bash
ng e2e
```

Angular CLI does not come with an end-to-end testing framework by default. You can choose one that suits your needs.

## Additional Resources

For more information on using the Angular CLI, including detailed command references, visit the [Angular CLI Overview and Command Reference](https://angular.dev/tools/cli) page.
=======
# 🏋️‍♂️ FitCity AI - Madrid Edition

**FitCity AI** es una plataforma web geolocalizada que transforma la experiencia de entrenamiento en Madrid. Mediante el uso de Inteligencia Artificial y Visión Artificial, actuamos como un juez virtual que valida tus levantamientos, cuenta tus repeticiones y te sitúa en rankings locales y globales. 

¡Compite con tu gimnasio y demuestra quién es el mejor de la ciudad!

---

## 🎯 Objetivo del Proyecto
El objetivo es gamificar el entrenamiento de fuerza y asegurar la validez técnica de los ejercicios. Los usuarios suben sus vídeos de entrenamiento, y nuestro sistema analiza la ejecución en tiempo real (o diferido) para generar métricas objetivas que alimentan un ranking por gimnasio y ejercicio.

## 🚀 Funcionalidades Principales (Fase 0)
- **Mapa Interactivo:** Localización de 5-10 gimnasios piloto en Madrid mediante OpenStreetMap.
- **Juez de IA:** Análisis de técnica y conteo de repeticiones mediante *Pose Estimation*.
- **Rankings Dinámicos:** Clasificaciones por ejercicio, peso levantado y calidad técnica.
- **Gamificación Local:** Representa a tu gimnasio y sube posiciones en el ranking de tu barrio.

## 🛠️ Stack Tecnológico

| Componente | Tecnología |
| :--- | :--- |
| **Frontend** | Angular + Leaflet/OpenStreetMap |
| **Backend** | FastAPI (Python) |
| **IA & Visión** | MediaPipe + LLM (Llama 3) |
| **Base de Datos** | Supabase (PostgreSQL) |
| **Despliegue** | Vercel / Docker |

---

## 🏗️ Arquitectura de Datos
El sistema procesa múltiples fuentes de información para garantizar un juicio justo:
1. **Vídeo:** Procesamiento temporal para detectar fases del movimiento.
2. **Keypoints:** Extracción del esqueleto corporal (33 puntos) con MediaPipe.
3. **Datos Tabulares:** Integración de peso cargado, repeticiones y score final.
4. **GeoJSON:** Datos espaciales de los gimnasios predefinidos en Madrid.



---

## 📋 Alcance (In/Out)
### ✅ En el radar (IN)
- Implementación inicial en Madrid (Piloto).
- Soporte para 3 ejercicios básicos (Sentadilla, Press Banca, Peso Muerto).
- Sistema de puntuación (Score) basado en técnica y carga.

### ❌ Fuera de alcance (OUT)
- Reconocimiento facial (privacidad priorizada).
- Almacenamiento de vídeos pesados (solo guardamos métricas).
- Expansión fuera de Madrid en esta fase.

---

## 🛡️ Gestión de Riesgos y Privacidad
- **Privacidad (Privacy by Design):** Para cumplir con la normativa, el sistema prioriza el procesamiento en tiempo real. **No almacenamos los vídeos de los usuarios**, solo las métricas y coordenadas resultantes.
- **Precisión:** Si la detección de pose falla, el sistema cuenta con un Plan B basado en validaciones simplificadas para asegurar la estabilidad.

---

## 👥 Organización del Equipo
El proyecto se divide en tres células de desarrollo:
- **Data & IA:** Desarrollo del modelo de pose estimation y lógica del juez.
- **Backend & Platform:** API, gestión de Supabase e integración del modelo.
- **Frontend & BI:** Interfaz de usuario, mapas y dashboards de rankings.

---

## 🚀 Próximos Pasos
1. [ ] Inicializar estructura del repositorio y dependencias.
2. [ ] Desplegar mapa base con gimnasios *mock* en Madrid.
3. [ ] Prototipo funcional de MediaPipe para validación de profundidad en sentadilla.
4. [ ] Diseño del esquema relacional en Supabase.
5. [ ] Definición matemática del algoritmo de *Scoring*.

---
📫 **FitCity AI** - Transformando el fitness madrileño con inteligencia.
>>>>>>> 2f2357ffac572cfde5065158398f928a19bd2651
