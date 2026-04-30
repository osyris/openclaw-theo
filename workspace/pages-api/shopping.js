/**
 * Shopping List API — server-side sync (like Tele2 tracker)
 *
 * GET  /shopping              — return shopping.json
 * POST /shopping/toggle       { category: 0, item: 1 }  — toggle checked
 * POST /shopping/clear        — remove all checked items
 */
module.exports = function(app, { readJSON, writeJSON }) {
    const DATA_PATH = 'app/shopping/shopping.json';

    app.get('/shopping', (req, res) => {
        const data = readJSON(DATA_PATH);
        if (!data) return res.status(500).json({ error: 'Could not read shopping.json' });
        res.json(data);
    });

    app.post('/shopping/toggle', (req, res) => {
        const { category, item } = req.body;
        if (category === undefined || item === undefined) {
            return res.status(400).json({ error: 'Missing category or item index' });
        }

        const data = readJSON(DATA_PATH);
        if (!data || !Array.isArray(data.categories)) {
            return res.status(500).json({ error: 'Could not read shopping.json' });
        }

        const cat = data.categories[category];
        if (!cat || !cat.items[item]) {
            return res.status(404).json({ error: 'Item not found' });
        }

        cat.items[item].checked = !cat.items[item].checked;
        data.updated = new Date().toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });

        writeJSON(DATA_PATH, data);

        res.json({ ok: true, category, item, checked: cat.items[item].checked });
    });

    app.post('/shopping/clear', (req, res) => {
        const data = readJSON(DATA_PATH);
        if (!data || !Array.isArray(data.categories)) {
            return res.status(500).json({ error: 'Could not read shopping.json' });
        }

        // Remove checked items from each category
        data.categories.forEach(cat => {
            cat.items = cat.items.filter(i => !i.checked);
        });
        // Remove empty categories
        data.categories = data.categories.filter(cat => cat.items.length > 0);
        data.updated = new Date().toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });

        writeJSON(DATA_PATH, data);

        res.json({ ok: true, categories: data.categories.length });
    });
};
