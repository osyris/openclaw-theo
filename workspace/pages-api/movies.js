/**
 * Movies API — toggle watched/liked status
 * 
 * POST /movies/toggle  { index: <number>, field: "watched"|"liked" }
 * GET  /movies         — return movies.json
 */
module.exports = function(app, { readJSON, writeJSON }) {
    const MOVIES_PATH = 'pages/movies/movies.json';

    app.get('/movies', (req, res) => {
        const movies = readJSON(MOVIES_PATH);
        if (!movies) return res.status(500).json({ error: 'Could not read movies.json' });
        res.json(movies);
    });

    app.post('/movies/toggle', (req, res) => {
        const { index, field } = req.body;

        if (typeof index !== 'number' || index < 0) {
            return res.status(400).json({ error: 'Invalid index' });
        }
        if (field !== 'watched' && field !== 'liked') {
            return res.status(400).json({ error: 'Field must be "watched" or "liked"' });
        }

        const movies = readJSON(MOVIES_PATH);
        if (!movies || !Array.isArray(movies)) {
            return res.status(500).json({ error: 'Could not read movies.json' });
        }
        if (index >= movies.length) {
            return res.status(400).json({ error: 'Index out of range' });
        }

        const movie = movies[index];

        if (field === 'watched') {
            movie.status = movie.status === 'watched' ? 'watchlist' : 'watched';
        } else if (field === 'liked') {
            movie.liked = !movie.liked;
        }

        writeJSON(MOVIES_PATH, movies);

        res.json({
            ok: true,
            index,
            title: movie.title,
            status: movie.status,
            liked: !!movie.liked
        });
    });
};
