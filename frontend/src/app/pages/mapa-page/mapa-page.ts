import { AfterViewInit, ChangeDetectionStrategy, Component, OnDestroy, ViewEncapsulation } from '@angular/core';

// Overpass: load fitness/gym nodes within a given bounding box
function buildOverpassQuery(south: number, west: number, north: number, east: number): string {
    const bbox = `${south},${west},${north},${east}`;
    return `
[out:json][timeout:25];
(
  node["leisure"="fitness_centre"](${bbox});
  node["amenity"="gym"](${bbox});
  node["sport"="fitness"](${bbox});
  way["leisure"="fitness_centre"](${bbox});
  way["amenity"="gym"](${bbox});
  way["leisure"="sports_centre"]["sport"="fitness"](${bbox});
);
out center;
`.trim();
}

// Grid cell key at ~5 km precision (0.05° ≈ 5 km)
function tileKey(lat: number, lon: number, precision = 0.05): string {
    return `${Math.floor(lat / precision)}_${Math.floor(lon / precision)}`;
}

@Component({
    selector: 'app-mapa-page',
    standalone: true,
    templateUrl: 'mapa-page.html',
    styleUrl: 'mapa-page.css',
    changeDetection: ChangeDetectionStrategy.OnPush,
    encapsulation: ViewEncapsulation.None,
})
export class MapaPage implements AfterViewInit, OnDestroy {

    private map: any = null;
    private maplibregl: any = null;
    private userMarker: any = null;
    private locating = false;

    /** Set of tile keys already fetched */
    private loadedTiles = new Set<string>();
    /** OSM node/way IDs already placed as markers */
    private placedIds = new Set<number>();
    /** Total count of markers on map */
    private totalCount = 0;
    /** True while an Overpass request is in flight */
    private fetching = false;
    /** Pending moveend timer (debounce) */
    private moveTimer: any = null;
    /** All markers on map (for cleanup) */
    private markers: any[] = [];

    ngAfterViewInit(): void {
        this.loadMapLibreAndInitMap();
    }

    ngOnDestroy(): void {
        if (this.map) this.map.remove();
    }

    /** Called by the "Mi ubicación" button */
    centerOnUser(): void {
        if (this.locating) return;
        this.setLocatingState(true);
        this.requestLocation(true);
    }

    private requestLocation(highAccuracy: boolean, isRetry = false): void {
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                this.setLocatingState(false);
                this.flyToUser(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy);
            },
            (err) => {
                // Si falla con alta precisión, reintentar con baja
                if (highAccuracy && !isRetry) {
                    console.warn('High accuracy failed, retrying with low accuracy...');
                    this.requestLocation(false, true);
                    return;
                }
                this.setLocatingState(false);
                const msgs: Record<number, string> = {
                    1: 'Permiso de ubicación denegado. Actívalo en tu navegador.',
                    2: 'Ubicación no disponible. Comprueba los ajustes de ubicación de tu Mac.',
                    3: 'Tiempo agotado. Inténtalo de nuevo.',
                };
                this.showError(msgs[err.code] || 'No se pudo obtener tu ubicación.');
            },
            { enableHighAccuracy: highAccuracy, timeout: 15000, maximumAge: 60000 }
        );
    }

    /** Fallback: geolocate by IP when browser geolocation fails */
    private fallbackIPGeolocation(): void {
        console.log('[FitCity Map] Trying IP geolocation fallback...');
        fetch('https://ipapi.co/json/')
            .then(res => res.json())
            .then((data: any) => {
                this.setLocatingState(false);
                if (data.latitude && data.longitude) {
                    console.log('[FitCity Map] IP location:', data.city, data.latitude, data.longitude);
                    this.flyToUser(data.latitude, data.longitude, 5000);
                } else {
                    this.loadVisibleArea();
                }
            })
            .catch(() => {
                this.setLocatingState(false);
                console.warn('[FitCity Map] IP geolocation also failed');
                this.loadVisibleArea();
            });
    }

    // ─────────────────────────────────────────────
    // MapLibre GL bootstrap
    // ─────────────────────────────────────────────

    private loadMapLibreAndInitMap(): void {
        // CSS
        if (!document.getElementById('maplibre-css')) {
            const link = document.createElement('link');
            link.id = 'maplibre-css';
            link.rel = 'stylesheet';
            link.href = 'https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css';
            document.head.appendChild(link);
        }

        // JS
        if ((window as any).maplibregl) {
            this.initMap();
            return;
        }

        if (!document.getElementById('maplibre-js')) {
            const script = document.createElement('script');
            script.id = 'maplibre-js';
            script.src = 'https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js';
            script.onload = () => this.initMap();
            document.head.appendChild(script);
        }
    }

    // ─────────────────────────────────────────────
    // Map init
    // ─────────────────────────────────────────────

    private initMap(): void {
        const mapEl = document.getElementById('map');
        if (!mapEl) return;

        const header = document.querySelector('.map-header') as HTMLElement | null;
        mapEl.style.height = (window.innerHeight - (header?.offsetHeight ?? 0)) + 'px';

        const ml = (window as any).maplibregl;
        this.maplibregl = ml;

        this.map = new ml.Map({
            container: 'map',
            style: 'https://tiles.openfreemap.org/styles/bright',
            center: [-3.7026, 40.4165],   // Madrid
            zoom: 14,
            pitch: 55,                     // 3D tilt!
            bearing: -15,                  // Slight rotation
            antialias: true,
        });

        // Navigation controls (rotate + zoom)
        this.map.addControl(new ml.NavigationControl({
            showCompass: true,
            showZoom: true,
            visualizePitch: true,
        }), 'top-right');

        // Allow toggling back to 3D view when clicking the compass in 2D mode
        setTimeout(() => this.setupCompassToggle(), 100);

        // Disable scroll zoom on touch to avoid conflicts with page scrolling
        this.map.scrollZoom.setWheelZoomRate(1 / 200);

        window.addEventListener('resize', () => {
            const h = document.querySelector('.map-header') as HTMLElement | null;
            mapEl.style.height = (window.innerHeight - (h?.offsetHeight ?? 0)) + 'px';
            this.map.resize();
        });

        this.map.on('load', () => {
            // ── 3D Buildings layer ──────────────────────────────────
            this.add3DBuildings();

            // ── Lazy load on pan/zoom (debounced 600 ms) ──
            this.map.on('moveend', () => {
                clearTimeout(this.moveTimer);
                this.moveTimer = setTimeout(() => this.loadVisibleArea(), 600);
            });

            // ── Try to start at user's location ──
            if ('geolocation' in navigator) {
                this.setLocatingState(true);
                navigator.geolocation.getCurrentPosition(
                    (pos) => {
                        this.setLocatingState(false);
                        this.flyToUser(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy);
                    },
                    (err) => {
                        console.warn('Geolocation browser error:', err.message);
                        // Fallback: intentar geolocalización por IP
                        this.fallbackIPGeolocation();
                    },
                    { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
                );
            } else {
                this.fallbackIPGeolocation();
            }
        });
    }

    // ─────────────────────────────────────────────
    // 3D Buildings
    // ─────────────────────────────────────────────

    private add3DBuildings(): void {
        // Check if there's a building source available in the style
        const layers = this.map.getStyle().layers;
        if (!layers) return;

        // Find the label layer to insert buildings below it
        let labelLayerId: string | undefined;
        for (const layer of layers) {
            if (layer.type === 'symbol' && (layer as any).layout?.['text-field']) {
                labelLayerId = layer.id;
                break;
            }
        }

        // Try to add 3D buildings from the existing vector source
        try {
            this.map.addLayer({
                'id': '3d-buildings',
                'source': 'openmaptiles',
                'source-layer': 'building',
                'type': 'fill-extrusion',
                'minzoom': 14,
                'paint': {
                    'fill-extrusion-color': [
                        'interpolate', ['linear'], ['get', 'render_height'],
                        0, '#d4d4d8',
                        50, '#a1a1aa',
                        100, '#71717a',
                    ],
                    'fill-extrusion-height': [
                        'interpolate', ['linear'], ['zoom'],
                        14, 0,
                        15.5, ['get', 'render_height']
                    ],
                    'fill-extrusion-base': [
                        'interpolate', ['linear'], ['zoom'],
                        14, 0,
                        15.5, ['get', 'render_min_height']
                    ],
                    'fill-extrusion-opacity': 0.7,
                },
            }, labelLayerId);
        } catch (e) {
            console.warn('Could not add 3D buildings layer:', e);
        }
    }

    // ─────────────────────────────────────────────
    // Viewport-based lazy loading
    // ─────────────────────────────────────────────

    private loadVisibleArea(): void {
        if (!this.map || this.fetching) return;

        const zoom = this.map.getZoom();
        console.log('[FitCity Map] loadVisibleArea — zoom:', zoom);
        if (zoom < 13) {
            this.showTileHint(true);
            return;
        }
        this.showTileHint(false);

        const bounds = this.map.getBounds();
        const south = bounds.getSouth();
        const west = bounds.getWest();
        const north = bounds.getNorth();
        const east = bounds.getEast();

        const precision = 0.05;
        const newTiles: Array<{ s: number; w: number; n: number; e: number }> = [];

        for (let lat = Math.floor(south / precision) * precision; lat < north; lat += precision) {
            for (let lon = Math.floor(west / precision) * precision; lon < east; lon += precision) {
                const key = tileKey(lat, lon, precision);
                if (!this.loadedTiles.has(key)) {
                    this.loadedTiles.add(key);
                    newTiles.push({
                        s: lat,
                        w: lon,
                        n: +(lat + precision).toFixed(6),
                        e: +(lon + precision).toFixed(6),
                    });
                }
            }
        }

        if (newTiles.length === 0) return;

        const mergedS = Math.min(...newTiles.map(t => t.s));
        const mergedW = Math.min(...newTiles.map(t => t.w));
        const mergedN = Math.max(...newTiles.map(t => t.n));
        const mergedE = Math.max(...newTiles.map(t => t.e));

        this.fetchFitnessCenters(mergedS, mergedW, mergedN, mergedE);
    }

    private fetchFitnessCenters(south: number, west: number, north: number, east: number): void {
        this.fetching = true;
        this.showChunkLoader(true);

        const query = buildOverpassQuery(south, west, north, east);
        const url = `https://overpass-api.de/api/interpreter?data=${encodeURIComponent(query)}`;
        const ml = this.maplibregl;

        console.log('[FitCity Map] Fetching gyms for bbox:', { south, west, north, east });

        fetch(url)
            .then(res => {
                console.log('[FitCity Map] Overpass response status:', res.status);
                return res.json();
            })
            .then((data: any) => {
                const elements: any[] = data.elements || [];
                console.log('[FitCity Map] Received', elements.length, 'elements from Overpass');

                for (const el of elements) {
                    if (this.placedIds.has(el.id)) continue;
                    this.placedIds.add(el.id);

                    let lat: number | undefined;
                    let lon: number | undefined;

                    if (el.type === 'node') { lat = el.lat; lon = el.lon; }
                    else if (el.center) { lat = el.center.lat; lon = el.center.lon; }
                    if (lat == null || lon == null) continue;

                    const name = el.tags?.name || 'Centro de fitness';
                    const address = [el.tags?.['addr:street'], el.tags?.['addr:housenumber']].filter(Boolean).join(', ');
                    const phone = el.tags?.phone || el.tags?.['contact:phone'] || '';
                    const web = el.tags?.website || el.tags?.['contact:website'] || '';
                    const opening = el.tags?.opening_hours || '';

                    // Create marker element — outer div for MapLibre positioning (NO transform!),
                    // inner div for visual styling and animation
                    const markerEl = document.createElement('div');
                    markerEl.className = 'gym-marker-wrap';
                    markerEl.innerHTML = '<div class="gym-marker"><span class="gym-marker-emoji">🏋️</span></div>';

                    // Popup HTML
                    const popupHTML = `
                        <div class="fitness-popup">
                            <h3>🏋️ ${name}</h3>
                            ${address ? `<p>📍 ${address}</p>` : ''}
                            ${opening ? `<p>🕐 ${opening}</p>` : ''}
                            ${phone ? `<p>📞 <a href="tel:${phone}">${phone}</a></p>` : ''}
                            ${web ? `<p>🌐 <a href="${web}" target="_blank" rel="noopener">Sitio web</a></p>` : ''}
                        </div>`;

                    const popup = new ml.Popup({
                        offset: [0, -42],
                        closeButton: true,
                        maxWidth: '250px',
                    }).setHTML(popupHTML);

                    const marker = new ml.Marker({ element: markerEl })
                        .setLngLat([lon, lat])
                        .setPopup(popup)
                        .addTo(this.map);

                    this.markers.push(marker);
                    this.totalCount++;
                }

                console.log('[FitCity Map] Total markers placed:', this.totalCount);
                this.updateCount(this.totalCount);
            })
            .catch((err) => {
                console.error('[FitCity Map] ERROR fetching gyms:', err);
                this.showError('Error al cargar centros. Inténtalo de nuevo.');
            })
            .finally(() => {
                this.fetching = false;
                this.showChunkLoader(false);
            });
    }

    // ─────────────────────────────────────────────
    // User location
    // ─────────────────────────────────────────────

    private flyToUser(lat: number, lon: number, accuracy: number): void {
        if (!this.map) return;
        const ml = this.maplibregl;

        // Remove old user marker
        if (this.userMarker) this.userMarker.remove();

        // Create user marker element
        const el = document.createElement('div');
        el.className = 'user-marker-3d';
        el.innerHTML = `
            <div class="um3-pulse"></div>
            <div class="um3-dot"></div>
        `;

        this.userMarker = new ml.Marker({ element: el, anchor: 'center' })
            .setLngLat([lon, lat])
            .addTo(this.map);

        // flyTo with 3D angle
        this.map.flyTo({
            center: [lon, lat],
            zoom: 15,
            pitch: 55,
            bearing: -15,
            speed: 1.2,
            curve: 1.5,
            essential: true,
        });
    }

    // ─────────────────────────────────────────────
    // UI helpers
    // ─────────────────────────────────────────────

    private setLocatingState(active: boolean): void {
        this.locating = active;
        const btn = document.getElementById('locate-btn') as HTMLButtonElement | null;
        if (!btn) return;
        btn.disabled = active;
        btn.classList.toggle('locating', active);
    }

    private showChunkLoader(visible: boolean): void {
        const el = document.getElementById('chunk-loader');
        if (el) el.style.opacity = visible ? '1' : '0';
    }

    private showTileHint(visible: boolean): void {
        const el = document.getElementById('zoom-hint');
        if (el) el.style.display = visible ? 'flex' : 'none';
    }

    private updateCount(count: number): void {
        const el = document.getElementById('fitness-count');
        if (el) el.textContent = `${count} centros`;
    }

    private showError(msg: string): void {
        const el = document.getElementById('map-error');
        if (el) { el.textContent = msg; el.style.display = 'block'; setTimeout(() => { el.style.display = 'none'; }, 4000); }
    }

    private setupCompassToggle(): void {
        const compassBtn = document.querySelector('.maplibregl-ctrl-compass');
        if (!compassBtn || !this.map) return;

        compassBtn.addEventListener('click', (e) => {
            const pitch = this.map.getPitch();
            // If current pitch is 0 (2D), clicking the compass (which usually resets to 0)
            // should instead toggle to 3D view.
            if (Math.round(pitch) === 0) {
                this.map.easeTo({
                    pitch: 55,
                    bearing: -15,
                    duration: 1000,
                    essential: true
                });
            }
        });
    }
}
