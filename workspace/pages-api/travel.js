/**
 * Travel Wishlist API — toggle visited status
 *
 * GET  /travel              — return places.json
 * POST /travel/toggle       { index: <number> }
 */
module.exports = function(app, { readJSON, writeJSON }) {
    const PLACES_PATH = 'app/travel-wishlist/places.json';

    app.get('/travel', (req, res) => {
        const places = readJSON(PLACES_PATH);
        if (!places) return res.status(500).json({ error: 'Could not read places.json' });
        res.json(places);
    });

    app.post('/travel/toggle', (req, res) => {
        const { index } = req.body;

        if (typeof index !== 'number' || index < 0) {
            return res.status(400).json({ error: 'Invalid index' });
        }

        const places = readJSON(PLACES_PATH);
        if (!places || !Array.isArray(places)) {
            return res.status(500).json({ error: 'Could not read places.json' });
        }
        if (index >= places.length) {
            return res.status(400).json({ error: 'Index out of range' });
        }

        places[index].visited = !places[index].visited;
        writeJSON(PLACES_PATH, places);

        res.json({
            ok: true,
            index,
            name: places[index].name,
            visited: places[index].visited
        });
    });

    app.post('/travel/toggle-spot', (req, res) => {
        const { index, spotIndex } = req.body;

        if (typeof index !== 'number' || typeof spotIndex !== 'number') {
            return res.status(400).json({ error: 'Invalid index or spotIndex' });
        }

        const places = readJSON(PLACES_PATH);
        if (!places || !Array.isArray(places)) {
            return res.status(500).json({ error: 'Could not read places.json' });
        }
        if (index >= places.length) {
            return res.status(400).json({ error: 'Index out of range' });
        }

        const spots = places[index].spots || [];
        if (spotIndex >= spots.length) {
            return res.status(400).json({ error: 'Spot index out of range' });
        }

        spots[spotIndex].visited = !spots[spotIndex].visited;
        writeJSON(PLACES_PATH, places);

        res.json({
            ok: true,
            index,
            spotIndex,
            name: spots[spotIndex].name,
            visited: spots[spotIndex].visited
        });
    });
};
