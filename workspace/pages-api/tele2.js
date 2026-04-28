/**
 * Tele2 Trial Tracker API — toggle closed status
 *
 * GET  /tele2         — return tele2.json
 * POST /tele2/toggle  { id: "<trial-id>" }  — toggle active/closed
 */
module.exports = function(app, { readJSON, writeJSON }) {
    const DATA_PATH = 'app/tele2/tele2.json';

    app.get('/tele2', (req, res) => {
        const data = readJSON(DATA_PATH);
        if (!data) return res.status(500).json({ error: 'Could not read tele2.json' });
        res.json(data);
    });

    app.post('/tele2/toggle', (req, res) => {
        const { id } = req.body;
        if (!id) return res.status(400).json({ error: 'Missing id' });

        const data = readJSON(DATA_PATH);
        if (!data || !Array.isArray(data.trials)) {
            return res.status(500).json({ error: 'Could not read tele2.json' });
        }

        const trial = data.trials.find(t => t.id === id);
        if (!trial) return res.status(404).json({ error: 'Trial not found' });

        trial.status = trial.status === 'closed' ? 'active' : 'closed';
        data.updated = new Date().toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });

        writeJSON(DATA_PATH, data);

        res.json({ ok: true, id, status: trial.status });
    });
};
