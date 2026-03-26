import { Injectable, signal } from '@angular/core';
import { API_URL } from './api.service';

export interface NearbyGym {
    id: number;
    name: string;
    distanceM: number;
    address: string;
    phone: string;
    web: string;
    opening_hours: string;
}

// ── Haversine distance in metres ──────────────────────────────────
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

/** Max displacement (metres) before we refetch gyms */
const CACHE_THRESHOLD_M = 500;

@Injectable({ providedIn: 'root' })
export class NearbyGymsService {

    /** The 5 nearest gyms, sorted by distance. Updated after each `load()` call. */
    readonly nearbyGyms = signal<NearbyGym[]>([]);
    readonly loading = signal<boolean>(false);
    readonly error = signal<string | null>(null);

    /** Cached location from the last successful fetch */
    private cachedLat: number | null = null;
    private cachedLon: number | null = null;

    /** Whether we already have valid cached results */
    get hasCachedData(): boolean {
        return this.cachedLat !== null && this.nearbyGyms().length > 0;
    }

    /**
     * Request the browser's geolocation and then load nearby gyms.
     * If the user has barely moved (<500 m) and we already have results,
     * skips the expensive Overpass fetch.
     */
    loadFromUserLocation(): void {
        if (this.loading()) return;

        if (!('geolocation' in navigator)) {
            this.error.set('Tu navegador no soporta geolocalización.');
            return;
        }

        // If we have cached data, silently check location first (no loader flash)
        if (this.hasCachedData) {
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    const dist = haversineM(
                        this.cachedLat!, this.cachedLon!,
                        pos.coords.latitude, pos.coords.longitude
                    );
                    if (dist < CACHE_THRESHOLD_M) {
                        // Close enough — reuse cached results, no fetch needed
                        console.log('[NearbyGyms] Using cached results (moved', Math.round(dist), 'm)');
                    } else {
                        // Moved significantly — refetch
                        console.log('[NearbyGyms] Location changed', Math.round(dist), 'm — refreshing');
                        this.load(pos.coords.latitude, pos.coords.longitude);
                    }
                },
                () => {
                    // Geolocation failed but we have cached data — keep showing it
                    console.warn('[NearbyGyms] Could not refresh location, using cached data');
                },
                { enableHighAccuracy: false, timeout: 8000, maximumAge: 120000 }
            );
            return;
        }

        // No cached data yet — show loader and fetch for the first time
        this.loading.set(true);
        this.error.set(null);

        navigator.geolocation.getCurrentPosition(
            (pos) => this.load(pos.coords.latitude, pos.coords.longitude),
            () => {
                this.loading.set(false);
                this.error.set('No se pudo obtener tu ubicación. Activa el permiso de localización.');
            },
            { enableHighAccuracy: false, timeout: 6000, maximumAge: 60000 }
        );
    }

    /**
     * Fetch gyms near a known coordinate pair.
     * Uses a ~1 km bounding box around the point.
     */
    load(lat: number, lon: number): void {
        const delta = 0.01;
        const south = lat - delta;
        const north = lat + delta;
        const west = lon - delta;
        const east = lon + delta;

        this.loading.set(true);
        this.error.set(null);

        fetchGymsProxy(south, west, north, east)
            .then((data: any) => {
                const elements: any[] = data.elements || [];
                const gyms: NearbyGym[] = [];

                for (const el of elements) {
                    let elLat: number | undefined;
                    let elLon: number | undefined;

                    if (el.type === 'node') { elLat = el.lat; elLon = el.lon; }
                    else if (el.center) { elLat = el.center.lat; elLon = el.center.lon; }
                    if (elLat == null || elLon == null) continue;

                    const tags = el.tags ?? {};
                    gyms.push({
                        id: el.id,
                        name: tags.name || 'Centro de fitness',
                        distanceM: Math.round(haversineM(lat, lon, elLat, elLon)),
                        address: [tags['addr:street'], tags['addr:housenumber']].filter(Boolean).join(' '),
                        phone: tags.phone || tags['contact:phone'] || '',
                        web: tags.website || tags['contact:website'] || '',
                        opening_hours: tags.opening_hours || '',
                    });
                }

                gyms.sort((a, b) => a.distanceM - b.distanceM);
                this.nearbyGyms.set(gyms.slice(0, 5));

                // Cache the successful location
                this.cachedLat = lat;
                this.cachedLon = lon;
            })
            .catch((err) => {
                console.error('[NearbyGymsService]', err);
                // If we have stale cached data, keep showing it instead of an error
                if (this.hasCachedData) {
                    console.warn('[NearbyGyms] Overpass failed — keeping cached results');
                } else {
                    this.error.set('No se pudieron cargar los gimnasios cercanos.');
                }
            })
            .finally(() => this.loading.set(false));
    }
}
