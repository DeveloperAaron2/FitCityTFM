import { Injectable, signal } from '@angular/core';

export interface NearbyGym {
    id: number;
    name: string;
    distanceM: number;
    address: string;
    phone: string;
    web: string;
    opening_hours: string;
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

function buildOverpassQuery(south: number, west: number, north: number, east: number): string {
    const bbox = `${south},${west},${north},${east}`;
    return `
[out:json][timeout:20];
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

@Injectable({ providedIn: 'root' })
export class NearbyGymsService {

    /** The 5 nearest gyms, sorted by distance. Updated after each `load()` call. */
    readonly nearbyGyms = signal<NearbyGym[]>([]);
    readonly loading = signal<boolean>(false);
    readonly error = signal<string | null>(null);

    /**
     * Request the browser's geolocation and then load nearby gyms.
     * Safe to call multiple times; ignores concurrent calls if already loading.
     */
    loadFromUserLocation(): void {
        if (this.loading()) return;

        if (!('geolocation' in navigator)) {
            this.error.set('Tu navegador no soporta geolocalización.');
            return;
        }

        this.loading.set(true);
        this.error.set(null);

        navigator.geolocation.getCurrentPosition(
            (pos) => this.load(pos.coords.latitude, pos.coords.longitude),
            () => {
                this.loading.set(false);
                this.error.set('No se pudo obtener tu ubicación. Activa el permiso de localización.');
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    }

    /**
     * Fetch gyms near a known coordinate pair.
     * Uses a ~3 km bounding box around the point.
     */
    load(lat: number, lon: number): void {
        // ~0.03° ≈ 3 km, gives a comfortable search radius
        const delta = 0.03;
        const south = lat - delta;
        const north = lat + delta;
        const west = lon - delta;
        const east = lon + delta;

        const query = buildOverpassQuery(south, west, north, east);
        const url = `https://overpass-api.de/api/interpreter?data=${encodeURIComponent(query)}`;

        this.loading.set(true);
        this.error.set(null);

        fetch(url)
            .then(res => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return res.json();
            })
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

                // Sort by distance and keep the 5 nearest
                gyms.sort((a, b) => a.distanceM - b.distanceM);
                this.nearbyGyms.set(gyms.slice(0, 5));
            })
            .catch((err) => {
                console.error('[NearbyGymsService]', err);
                this.error.set('No se pudieron cargar los gimnasios cercanos.');
            })
            .finally(() => this.loading.set(false));
    }
}
