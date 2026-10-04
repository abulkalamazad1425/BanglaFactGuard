async function database() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('bfg-drafts', 1);
    request.onupgradeneeded = () => request.result.createObjectStore('images');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
export async function imageStore(key, value) {
  const db = await database();
  return new Promise((resolve, reject) => {
    const tx = db.transaction('images', value === undefined ? 'readonly' : 'readwrite');
    const store = tx.objectStore('images');
    const req = value === undefined ? store.get(key) : value === null ? store.delete(key) : store.put(value, key);
    tx.oncomplete = () => { db.close(); resolve(req.result); };
    tx.onerror = () => { db.close(); reject(tx.error); };
  });
}
