const endpoints = [
    'https://overpass.kumi.systems/api/interpreter',
    'https://overpass-api.de/api/interpreter',
    'https://lz4.overpass-api.de/api/interpreter',
    'https://overpass.openstreetmap.fr/api/interpreter',
];
const query = `[out:json][timeout:25];(way["leisure"="sports_centre"]["sport"="fitness"](40.41,-3.71,40.42,-3.70););out center;`;
const encoded = encodeURIComponent(query);

async function test() {
    for (const ep of endpoints) {
        try {
            console.log(`Testing ${ep}...`);
            const res = await fetch(`${ep}?data=${encoded}`);
            console.log(`  Status: ${res.status}`);
            if (res.ok) {
                const data = await res.json();
                console.log(`  Success! Elements: ${data.elements?.length}`);
            }
        } catch (e) {
            console.error(`  Error: ${e.message}`);
        }
    }
}
test();
