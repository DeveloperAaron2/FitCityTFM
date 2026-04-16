import { AfterViewInit, ChangeDetectionStrategy, Component, OnDestroy, ViewEncapsulation, inject, ChangeDetectorRef } from '@angular/core';
import { Router } from '@angular/router';
import { API_URL, ApiService } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';

// Grid cell key at ~5 km precision (0.05° ≈ 5 km)
function tileKey(lat: number, lon: number, precision = 0.05): string {
    return `${Math.floor(lat / precision)}_${Math.floor(lon / precision)}`;
}

function haversineM(lat1: number, lon1: number, lat2: number, lon2: number): number {
    const R = 6371000;
    const toRad = (v: number) => (v * Math.PI) / 180;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a =
        Math.sin(dLat / 2) ** 2 +
        Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/** 
 * Fetch gyms from the Python Backend Proxy.
 * The backend manages Overpass requests and caching to prevent 504 Gateway Timeouts.
 */
async function fetchGymsProxy(south: number, west: number, north: number, east: number): Promise<any> {
    const url = `${API_URL}/gyms/nearby?south=${south}&west=${west}&north=${north}&east=${east}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
}

/** Max displacement (metres) before we re-localise on map open */
const CACHE_THRESHOLD_M = 500;

/**
 * Persistent cross-navigation cache for the map page.
 * Stored as a module-level object so it survives Angular route changes.
 */
const mapCache: {
    userLat: number | null;
    userLon: number | null;
    mapCenter: [number, number] | null;
    mapZoom: number | null;
    mapPitch: number | null;
    mapBearing: number | null;
    loadedTiles: Set<string>;
    placedIds: Set<number>;
    placedGyms: Array<{ lat: number; lon: number; tags: any }>;
    totalCount: number;
} = {
    userLat: null,
    userLon: null,
    mapCenter: null,
    mapZoom: null,
    mapPitch: null,
    mapBearing: null,
    loadedTiles: new Set<string>(),
    placedIds: new Set<number>(),
    placedGyms: [],
    totalCount: 0,
};

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

    private api = inject(ApiService);
    private auth = inject(AuthService);
    private router = inject(Router);
    private cdr = inject(ChangeDetectorRef);

    isSearchingLocation = false;
    isSearchExpanded = false;

    toggleSearch(): void {
        this.isSearchExpanded = !this.isSearchExpanded;
        this.cdr.markForCheck();
        if (this.isSearchExpanded) {
            setTimeout(() => {
                const input = document.getElementById('searchInputField');
                if (input) {
                    input.focus();
                }
            }, 100);
        }
    }

    // Instance-level references to shared cache sets
    private get loadedTiles() { return mapCache.loadedTiles; }
    private get placedIds() { return mapCache.placedIds; }
    private markers: any[] = [];

    private fetching = false;
    private moveTimer: any = null;

    // Store gym names visited today to persist UI state
    private visitedTodayGyms = new Set<string>();

    ngAfterViewInit(): void {
        const user = this.auth.user();
        if (user && user.id) {
            this.api.getGymVisits(user.id).subscribe({
                next: (visits: any[]) => {
                    const today = new Date().toISOString().split('T')[0];
                    for (const v of visits) {
                        if (v.visited_at === today && v.gym_name) {
                            this.visitedTodayGyms.add(v.gym_name);
                        }
                    }
                    this.loadMapLibreAndInitMap();
                },
                error: (err) => {
                    console.warn('[FitCity Map] Failed to fetch daily visits', err);
                    this.loadMapLibreAndInitMap();
                }
            });
        } else {
            this.loadMapLibreAndInitMap();
        }
    }

    ngOnDestroy(): void {
        // Save current map view to cache before destroying
        if (this.map) {
            const center = this.map.getCenter();
            mapCache.mapCenter = [center.lng, center.lat];
            mapCache.mapZoom = this.map.getZoom();
            mapCache.mapPitch = this.map.getPitch();
            mapCache.mapBearing = this.map.getBearing();
            this.map.remove();
            this.map = null;
        }
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
                const newLat = pos.coords.latitude;
                const newLon = pos.coords.longitude;
                mapCache.userLat = newLat;
                mapCache.userLon = newLon;
                this.flyToUser(newLat, newLon, pos.coords.accuracy);
            },
            (err) => {
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

    private fallbackIPGeolocation(): void {
        console.log('[FitCity Map] Trying IP geolocation fallback...');
        fetch('https://ipapi.co/json/')
            .then(res => res.json())
            .then((data: any) => {
                this.setLocatingState(false);
                if (data.latitude && data.longitude) {
                    console.log('[FitCity Map] IP location:', data.city, data.latitude, data.longitude);
                    mapCache.userLat = data.latitude;
                    mapCache.userLon = data.longitude;
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
        if (!document.getElementById('maplibre-css')) {
            const link = document.createElement('link');
            link.id = 'maplibre-css';
            link.rel = 'stylesheet';
            link.href = 'https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css';
            document.head.appendChild(link);
        }

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
        } else {
            // Script tag exists but maplibregl isn't ready yet — poll
            const poll = setInterval(() => {
                if ((window as any).maplibregl) {
                    clearInterval(poll);
                    this.initMap();
                }
            }, 100);
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

        // Restore last view position if cached, otherwise start at Madrid
        const initialCenter: [number, number] = mapCache.mapCenter ?? [-3.7026, 40.4165];
        const initialZoom = mapCache.mapZoom ?? 14;
        const initialPitch = mapCache.mapPitch ?? 55;
        const initialBearing = mapCache.mapBearing ?? -15;

        this.map = new ml.Map({
            container: 'map',
            style: 'https://tiles.openfreemap.org/styles/bright',
            center: initialCenter,
            zoom: initialZoom,
            pitch: initialPitch,
            bearing: initialBearing,
            antialias: true,
        });

        this.map.addControl(new ml.NavigationControl({
            showCompass: true,
            showZoom: true,
            visualizePitch: true,
        }), 'top-right');

        // Allow toggling back to 3D view when clicking the compass in 2D mode
        setTimeout(() => this.setupCompassToggle(), 100);

        this.map.scrollZoom.setWheelZoomRate(1 / 200);

        window.addEventListener('resize', () => {
            const h = document.querySelector('.map-header') as HTMLElement | null;
            mapEl.style.height = (window.innerHeight - (h?.offsetHeight ?? 0)) + 'px';
            this.map.resize();
        });

        this.map.on('load', () => {
            this.add3DBuildings();

            // Re-render cached markers (if any) without re-fetching
            if (mapCache.placedGyms.length > 0) {
                console.log('[FitCity Map] Restoring', mapCache.placedGyms.length, 'cached gym markers');
                this.updateCount(mapCache.totalCount);
                for (const gym of mapCache.placedGyms) {
                    this.addMarker(gym.lat, gym.lon, gym.tags, gym.lat, gym.lon);
                }
            }

            // Lazy load on pan/zoom (debounced 600 ms)
            this.map.on('moveend', () => {
                clearTimeout(this.moveTimer);
                this.moveTimer = setTimeout(() => this.loadVisibleArea(), 600);
            });

            // ── Decide whether to re-localise ──────────────────────
            const hasCachedLocation = mapCache.userLat !== null && mapCache.userLon !== null;

            if (hasCachedLocation) {
                // Silently check if user has moved significantly
                if ('geolocation' in navigator) {
                    navigator.geolocation.getCurrentPosition(
                        (pos) => {
                            const dist = haversineM(
                                mapCache.userLat!, mapCache.userLon!,
                                pos.coords.latitude, pos.coords.longitude
                            );
                            if (dist >= CACHE_THRESHOLD_M) {
                                console.log('[FitCity Map] Moved', Math.round(dist), 'm — re-localising');
                                mapCache.userLat = pos.coords.latitude;
                                mapCache.userLon = pos.coords.longitude;
                                this.flyToUser(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy);
                            } else {
                                console.log('[FitCity Map] Using cached location (', Math.round(dist), 'm away)');
                                // Place user marker at cached position without flying
                                this.placeUserMarker(mapCache.userLat!, mapCache.userLon!);
                                // Load any visible tiles not yet fetched
                                this.loadVisibleArea();
                            }
                        },
                        () => {
                            // Can't get new location — stay at cached position
                            this.placeUserMarker(mapCache.userLat!, mapCache.userLon!);
                            this.loadVisibleArea();
                        },
                        { enableHighAccuracy: false, timeout: 8000, maximumAge: 120000 }
                    );
                } else {
                    this.placeUserMarker(mapCache.userLat!, mapCache.userLon!);
                    this.loadVisibleArea();
                }
            } else {
                // First visit — full geolocation flow
                if ('geolocation' in navigator) {
                    this.setLocatingState(true);
                    navigator.geolocation.getCurrentPosition(
                        (pos) => {
                            this.setLocatingState(false);
                            mapCache.userLat = pos.coords.latitude;
                            mapCache.userLon = pos.coords.longitude;
                            this.flyToUser(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy);
                        },
                        (err) => {
                            console.warn('Geolocation browser error:', err.message);
                            this.fallbackIPGeolocation();
                        },
                        { enableHighAccuracy: false, timeout: 5000, maximumAge: 60000 }
                    );
                } else {
                    this.fallbackIPGeolocation();
                }
            }
        });
    }

    // ─────────────────────────────────────────────
    // 3D Buildings
    // ─────────────────────────────────────────────

    private add3DBuildings(): void {
        const layers = this.map.getStyle().layers;
        if (!layers) return;

        let labelLayerId: string | undefined;
        for (const layer of layers) {
            if (layer.type === 'symbol' && (layer as any).layout?.['text-field']) {
                labelLayerId = layer.id;
                break;
            }
        }

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

        console.log('[FitCity Map] Fetching gyms for bbox:', { south, west, north, east });

        fetchGymsProxy(south, west, north, east)
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

                    const tags = el.tags ?? {};
                    this.addMarker(lat, lon, tags, lat, lon);

                    // Cache for re-render on revisit
                    mapCache.placedGyms.push({ lat, lon, tags });
                    mapCache.totalCount++;
                }

                console.log('[FitCity Map] Total markers placed:', mapCache.totalCount);
                this.updateCount(mapCache.totalCount);
            })
            .catch((err) => {
                console.error('[FitCity Map] ERROR fetching gyms after retries:', err);
                this.showError('Error al cargar centros. Se reintentará en la próxima apertura.');
            })
            .finally(() => {
                this.fetching = false;
                this.showChunkLoader(false);
            });
    }

    // ─────────────────────────────────────────────
    // Marker helpers
    // ─────────────────────────────────────────────

    private addMarker(lat: number, lon: number, tags: any, _refLat: number, _refLon: number): void {
        const ml = this.maplibregl;
        if (!ml || !this.map) return;

        const name = tags?.name || 'Centro de fitness';
        const address = [tags?.['addr:street'], tags?.['addr:housenumber']].filter(Boolean).join(', ');
        const phone = tags?.phone || tags?.['contact:phone'] || '';
        const web = tags?.website || tags?.['contact:website'] || '';
        const opening = tags?.opening_hours || '';

        const markerEl = document.createElement('div');
        markerEl.className = 'gym-marker-wrap';
        const isVisited = this.visitedTodayGyms.has(name);
        if (isVisited) {
            markerEl.innerHTML = '<div class="gym-marker gym-marker-visited"><span class="gym-marker-emoji">🏋️</span></div>';
        } else {
            markerEl.innerHTML = '<div class="gym-marker"><span class="gym-marker-emoji">🏋️</span></div>';
        }

        const popup = new ml.Popup({
            offset: [0, -42],
            closeButton: true,
            maxWidth: '250px',
        });

        popup.on('open', () => {
            const popupContent = document.createElement('div');
            popupContent.className = 'fitness-popup';
            popupContent.innerHTML = `
                <h3>🏋️ ${name}</h3>
                ${address ? `<p>📍 ${address}</p>` : ''}
                ${opening ? `<p>🕐 ${opening}</p>` : ''}
                ${phone ? `<p>📞 <a href="tel:${phone}">${phone}</a></p>` : ''}
                ${web ? `<p>🌐 <a href="${web}" target="_blank" rel="noopener">Sitio web</a></p>` : ''}
            `;

            const visitBtn = document.createElement('button');
            visitBtn.className = 'visit-gym-btn map-visit-btn';

            if (this.visitedTodayGyms.has(name)) {
                visitBtn.innerText = '¡Visitado! ✓';
                visitBtn.classList.add('visited-success');
                visitBtn.disabled = true;
                popupContent.appendChild(visitBtn);
            } else {
                const uLat = mapCache.userLat;
                const uLon = mapCache.userLon;
                if (uLat !== null && uLon !== null) {
                    const distance = haversineM(uLat, uLon, lat, lon);
                    if (distance <= 150) {
                        visitBtn.innerText = 'Marcar como visitado';
                        visitBtn.onclick = () => this.visitGym(name, address, lat, lon, visitBtn, markerEl);
                        popupContent.appendChild(visitBtn);
                    }
                }
            }

            // Navigate to ranking when clicking on the popup body
            popupContent.onclick = (e) => {
                const target = e.target as HTMLElement;
                if (target.tagName === 'A' || target.closest('a') || target.tagName === 'BUTTON' || target.closest('button')) {
                    return; 
                }
                this.router.navigate(['/ranking'], { queryParams: { tab: 'gyms', gym: name } });
            };

            popup.setDOMContent(popupContent);
        });

        const marker = new ml.Marker({ element: markerEl })
            .setLngLat([lon, lat])
            .setPopup(popup)
            .addTo(this.map);

        this.markers.push(marker);
    }

    private visitGym(name: string, address: string, lat: number, lon: number, btn: HTMLButtonElement, markerEl: HTMLElement): void {
        const user = this.auth.user();
        if (!user || !user.id) {
            this.showError('Debes iniciar sesión para visitar un centro.');
            return;
        }

        if (mapCache.userLat !== null && mapCache.userLon !== null) {
            const distance = haversineM(mapCache.userLat, mapCache.userLon, lat, lon);
            if (distance > 150) {
                this.showError(`Estás a ${Math.round(distance)}m. Debes estar a menos de 150m para visitar el gimnasio.`);
                return;
            }
        } else {
            this.showError('No se pudo verificar tu ubicación actual.');
            return;
        }

        btn.disabled = true;
        btn.innerText = 'Registrando...';

        this.api.createGymVisit(user.id, {
            gym_name: name,
            gym_address: address,
            gym_lat: lat,
            gym_lon: lon
        }).subscribe({
            next: (res) => {
                btn.innerText = '¡Visitado! ✓';
                btn.classList.add('visited-success');
                this.visitedTodayGyms.add(name);
                
                // Update marker visual dynamically
                const innerMarker = markerEl.querySelector('.gym-marker');
                if (innerMarker) {
                    innerMarker.classList.add('gym-marker-visited');
                }
                
                // Add positive visual feedback and optionally update the local XP manually if it's synced
                if (res.xp_awarded) {
                    const currentXp = user.current_xp || 0;
                    this.auth.updateUser({ current_xp: currentXp + res.xp_awarded });
                }
            },
            error: (err) => {
                btn.disabled = false;
                btn.innerText = 'Marcar como visitado';
                this.showError('Error al registrar la visita.');
            }
        });
    }

    // ─────────────────────────────────────────────
    // User location
    // ─────────────────────────────────────────────

    /** Place user marker at coords WITHOUT flying to it */
    private placeUserMarker(lat: number, lon: number): void {
        if (!this.map) return;
        const ml = this.maplibregl;
        if (this.userMarker) this.userMarker.remove();

        const el = document.createElement('div');
        el.className = 'user-marker-3d';
        el.innerHTML = `
            <div class="um3-pulse"></div>
            <div class="um3-dot"></div>
        `;

        this.userMarker = new ml.Marker({ element: el, anchor: 'center' })
            .setLngLat([lon, lat])
            .addTo(this.map);
    }

    private flyToUser(lat: number, lon: number, accuracy: number): void {
        if (!this.map) return;
        this.placeUserMarker(lat, lon);

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

    async searchLocation(query: string) {
        if (!query || query.trim() === '') return;
        this.isSearchingLocation = true;
        this.cdr.markForCheck();
        
        try {
            const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=10&countrycodes=es`;
            const res = await fetch(url);
            const data = await res.json();
            
            const validTypes = ['city', 'town', 'village', 'municipality', 'province', 'state', 'county', 'region', 'administrative'];
            const validResult = data.find((item: any) => {
                const type = item.type || item.addresstype || '';
                if (item.class === 'boundary' && type === 'administrative') return true;
                if (item.class === 'place' && validTypes.includes(type)) return true;
                return false;
            });
            
            if (validResult) {
                const lat = parseFloat(validResult.lat);
                const lon = parseFloat(validResult.lon);
                if (this.map) {
                    this.map.flyTo({
                        center: [lon, lat],
                        zoom: 13,
                        essential: true
                    });
                    // Close the search overlay upon success
                    this.isSearchExpanded = false;
                    
                    // Clear the input field
                    const input = document.getElementById('searchInputField') as HTMLInputElement | null;
                    if (input) {
                        input.value = '';
                    }
                }
            } else {
                this.showError('Lugar no encontrado o a las afueras de España');
            }
        } catch (err) {
            console.error('[FitCity Map] Error searching location:', err);
            this.showError('Error al buscar la ubicación.');
        } finally {
            this.isSearchingLocation = false;
            this.cdr.detectChanges();
        }
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
