import { AfterViewInit, ChangeDetectionStrategy, Component, ViewEncapsulation } from '@angular/core';

declare const L: any;

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
function tileKey(lat: number, lon: number, precision = 0.15): string {
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
export class MapaPage implements AfterViewInit {

    private leafletMap: any = null;
    private userMarker: any = null;
    private userCircle: any = null;
    private locating = false;
    private fitnessIcon: any = null;

    /** Set of tile keys already fetched, to avoid redundant requests */
    private loadedTiles = new Set<string>();
    /** OSM node/way IDs already placed as markers, to avoid duplicates */
    private placedIds = new Set<number>();
    /** Total count of markers on map */
    private totalCount = 0;
    /** True while an Overpass request is in flight */
    private fetching = false;
    /** Pending moveend timer (debounce) */
    private moveTimer: any = null;

    ngAfterViewInit(): void {
        this.loadLeafletAndInitMap();
    }

    /** Called by the "Mi ubicación" button */
    centerOnUser(): void {
        if (this.locating) return;
        this.setLocatingState(true);
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                this.setLocatingState(false);
                this.flyToUser(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy);
            },
            () => {
                this.setLocatingState(false);
                this.showError('No se pudo obtener tu ubicación.');
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    }

    // ─────────────────────────────────────────────
    // Leaflet bootstrap
    // ─────────────────────────────────────────────

    private loadLeafletAndInitMap(): void {
        if (!document.getElementById('leaflet-css')) {
            const link = document.createElement('link');
            link.id = 'leaflet-css';
            link.rel = 'stylesheet';
            link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
            document.head.appendChild(link);
        }

        if (typeof (window as any).L !== 'undefined') {
            this.initMap();
            return;
        }

        if (!document.getElementById('leaflet-js')) {
            const script = document.createElement('script');
            script.id = 'leaflet-js';
            script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
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

        const Leaflet = (window as any).L;
        const madridCenter: [number, number] = [40.4165, -3.7026];

        this.leafletMap = Leaflet.map('map', { center: madridCenter, zoom: 13, zoomControl: true });

        Leaflet.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19,
        }).addTo(this.leafletMap);

        window.addEventListener('resize', () => {
            const h = document.querySelector('.map-header') as HTMLElement | null;
            mapEl.style.height = (window.innerHeight - (h?.offsetHeight ?? 0)) + 'px';
            this.leafletMap.invalidateSize();
        });

        this.fitnessIcon = Leaflet.divIcon({
            className: '',
            html: `<div class="fitness-marker"><span>🏋️</span></div>`,
            iconSize: [36, 36],
            iconAnchor: [18, 36],
            popupAnchor: [0, -36],
        });

        // ── Lazy load on pan/zoom (debounced 600 ms) ──
        this.leafletMap.on('moveend', () => {
            clearTimeout(this.moveTimer);
            this.moveTimer = setTimeout(() => this.loadVisibleArea(), 600);
        });

        // ── Try to start at user's location, otherwise load initial view ──
        if ('geolocation' in navigator) {
            this.setLocatingState(true);
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    this.setLocatingState(false);
                    // flyTo triggers moveend → loadVisibleArea automatically
                    this.flyToUser(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy);
                },
                () => {
                    this.setLocatingState(false);
                    // No location permission → load Madrid center view
                    this.loadVisibleArea();
                },
                { enableHighAccuracy: true, timeout: 8000 }
            );
        } else {
            this.loadVisibleArea();
        }
    }

    // ─────────────────────────────────────────────
    // Viewport-based lazy loading
    // ─────────────────────────────────────────────

    private loadVisibleArea(): void {
        if (!this.leafletMap || this.fetching) return;

        // Only fetch when zoomed in enough (avoid giant queries on zoom-out)
        const zoom = this.leafletMap.getZoom();
        if (zoom < 11) {
            this.showTileHint(true);
            return;
        }
        this.showTileHint(false);

        const bounds = this.leafletMap.getBounds();
        const south = bounds.getSouth();
        const west = bounds.getWest();
        const north = bounds.getNorth();
        const east = bounds.getEast();

        // Split the viewport into 0.15° grid cells and fetch only the new ones
        const precision = 0.15;
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

        // Merge tiles into a single slightly-padded bbox to minimise requests
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
        const Leaflet = (window as any).L;

        fetch(url)
            .then(res => res.json())
            .then((data: any) => {
                const elements: any[] = data.elements || [];

                for (const el of elements) {
                    // Skip duplicates
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

                    const popup = `
                        <div class="fitness-popup">
                            <h3>🏋️ ${name}</h3>
                            ${address ? `<p>📍 ${address}</p>` : ''}
                            ${opening ? `<p>🕐 ${opening}</p>` : ''}
                            ${phone ? `<p>📞 <a href="tel:${phone}">${phone}</a></p>` : ''}
                            ${web ? `<p>🌐 <a href="${web}" target="_blank" rel="noopener">Sitio web</a></p>` : ''}
                        </div>`;

                    Leaflet.marker([lat, lon], { icon: this.fitnessIcon })
                        .addTo(this.leafletMap)
                        .bindPopup(popup);

                    this.totalCount++;
                }

                this.updateCount(this.totalCount);
            })
            .catch(() => this.showError('Error al cargar centros. Inténtalo de nuevo.'))
            .finally(() => {
                this.fetching = false;
                this.showChunkLoader(false);
            });
    }

    // ─────────────────────────────────────────────
    // User location
    // ─────────────────────────────────────────────

    private flyToUser(lat: number, lon: number, accuracy: number): void {
        if (!this.leafletMap) return;
        const Leaflet = (window as any).L;

        if (this.userMarker) this.leafletMap.removeLayer(this.userMarker);
        if (this.userCircle) this.leafletMap.removeLayer(this.userCircle);

        const userIcon = Leaflet.divIcon({
            className: '',
            html: `<div class="user-marker"><div class="user-marker-dot"></div><div class="user-marker-pulse"></div></div>`,
            iconSize: [20, 20],
            iconAnchor: [10, 10],
        });

        this.userMarker = Leaflet.marker([lat, lon], { icon: userIcon, zIndexOffset: 1000 })
            .addTo(this.leafletMap)
            .bindPopup('<div class="fitness-popup"><h3>📍 Tu ubicación</h3></div>');

        this.userCircle = Leaflet.circle([lat, lon], {
            radius: Math.min(accuracy, 300),
            color: '#3b82f6', fillColor: '#3b82f6', fillOpacity: 0.12, weight: 1.5,
        }).addTo(this.leafletMap);

        // flyTo triggers moveend → loadVisibleArea
        this.leafletMap.flyTo([lat, lon], 14, { duration: 1.2 });
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
}
