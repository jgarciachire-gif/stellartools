const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

function worker({ storageFailure = false } = {}) {
    const handlers = {}, entries = new Map();
    let calls = 0;
    const response = () => ({ ok: true, type: 'basic', clone() { return this; } });
    vm.runInNewContext(fs.readFileSync('static/service-worker.js', 'utf8'), {
        self: { location: { origin: 'https://app.test' }, addEventListener: (name, fn) => handlers[name] = fn },
        caches: { open: async () => ({
            match: async req => entries.get(req.url),
            put: async (req, value) => {
                if (storageFailure) throw Error('quota');
                entries.set(req.url, value);
            }
        }) },
        fetch: async () => { calls++; return response(); }, URL, Set, Response,
    });
    return {
        calls: () => calls,
        async request(path, method = 'GET') {
            let result;
            const pending = [];
            handlers.fetch({ request: { url: new URL(path, 'https://app.test').href, method },
                respondWith: promise => result = promise, waitUntil: promise => pending.push(promise) });
            const answer = await result;
            await Promise.all(pending);
            return answer;
        }
    };
}

test('versioned assets reuse cache and a new revision downloads once', async () => {
    const sw = worker();
    await sw.request('/static/app.js?v=deploy-abc-123');
    await sw.request('/static/app.js?v=deploy-abc-123');
    assert.equal(sw.calls(), 1);
    await sw.request('/static/app.js?v=deploy-def-123');
    assert.equal(sw.calls(), 2);
});

test('unversioned files continue revalidating', async () => {
    const sw = worker();
    await sw.request('/static/app.js');
    await sw.request('/static/app.js');
    assert.equal(sw.calls(), 2);
});

test('private pages, API, external assets and mutations bypass cache', async () => {
    const sw = worker();
    for (const path of ['/analisis-pedido', '/api/productos', '/service-worker.js',
        '/static/private.html', 'https://other.test/static/app.js']) {
        assert.equal(await sw.request(path), undefined);
    }
    assert.equal(await sw.request('/static/app.js', 'POST'), undefined);
    assert.equal(sw.calls(), 0);
});

test('full or unavailable cache does not discard a valid network response', async () => {
    const sw = worker({ storageFailure: true });
    assert.equal((await sw.request('/static/app.js?v=deploy-abc-123')).ok, true);
});
