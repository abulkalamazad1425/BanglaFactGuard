import {
  DEFAULTS,
  ownerOf,
  ready,
  terminal,
  summarize,
  cropRect,
  validateDraft,
  withoutDateWarnings,
  headlinePreview,
  HttpError,
  isDeletedOnServer,
  recheckDelay,
} from './shared.js';
import { imageStore } from './db.js';
import { selectArea } from './capture.js';

const ITEM = 'claim:';
let refreshing,
  polling,
  submitting = false,
  submissionQueued = false;
let operations = Promise.resolve();
// Serialize account/configuration mutations with network work, including alarms.
function exclusive(operation) {
  const result = operations.then(operation);
  operations = result.catch(() => {});
  return result;
}
const read = async (key) => (await chrome.storage.local.get(key))[key];
const config = async () => ({ ...DEFAULTS, ...(await read('settings')) });
const auth = () => read('auth');
async function requireOn() {
  if (!(await config()).enabled) throw Error('Turn on BanglaFactGuard to continue.');
}
async function request(path, { method = 'GET', body, anonymous = false, retry = true } = {}) {
  const cfg = await config(),
    session = anonymous ? null : await auth();
  const headers = {};
  if (session?.access_token) headers.Authorization = `Bearer ${session.access_token}`;
  if (body && !(body instanceof FormData)) headers['Content-Type'] = 'application/json';
  let response;
  try {
    response = await fetch(cfg.api + path, {
      method,
      headers,
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(25000),
    });
  } catch {
    throw Error(
      'Cannot reach the server. Check your connection and API address. If you ' +
        'were submitting, acceptance is uncertain: check Activity or website ' +
        'history before retrying.',
    );
  }
  if (response.status === 401 && session && retry) {
    refreshing ||= (async () => {
      const res = await fetch(cfg.api + '/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: session.refresh_token }),
        signal: AbortSignal.timeout(15000),
      });
      if (!res.ok) {
        if ([401, 403].includes(res.status)) {
          await chrome.storage.local.remove('auth');
          throw Error('Your session expired. Please sign in again.');
        }
        throw Error('Sign-in could not be refreshed. Please try again shortly.');
      }
      const tokens = await res.json();
      await chrome.storage.local.set({ auth: { ...session, ...tokens } });
    })().finally(() => {
      refreshing = null;
    });
    await refreshing;
    return request(path, { method, body, anonymous, retry: false });
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = data.detail;
    throw new HttpError(
      typeof detail === 'string'
        ? detail
        : detail?.message ||
            (Array.isArray(detail)
              ? detail.map((x) => x.msg).join('; ')
              : `Server request failed (${response.status}).`),
      response.status,
      detail,
    );
  }
  return response.status === 204 ? null : response.json();
}
async function items() {
  const all = await chrome.storage.local.get(null);
  const owner = ownerOf(await auth());
  return Object.entries(all)
    .filter(([key, value]) => key.startsWith(ITEM) && value.owner === owner)
    .map(([, value]) =>
      value.type === 'PHOTO_CARD' && value.summary
        ? {
            ...value,
            summary: { ...value.summary, warnings: withoutDateWarnings(value.summary.warnings) },
          }
        : value,
    )
    .sort((a, b) => b.created - a.created);
}
async function badge() {
  const count = (await items()).filter((x) => x.unread).length;
  const cfg = await config();
  await chrome.action.setBadgeBackgroundColor({ color: '#1f7f4e' });
  await chrome.action.setBadgeText({ text: cfg.enabled ? (count ? String(count) : '') : 'OFF' });
}
async function setup() {
  await chrome.storage.local.setAccessLevel({ accessLevel: 'TRUSTED_CONTEXTS' });
  // Use an explicit toolbar action to obtain activeTab before opening the panel.
  // A click inside an already-open side panel does not grant access to a new site.
  await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: false });
  if (!(await chrome.alarms.get('check-results')))
    await chrome.alarms.create('check-results', { periodInMinutes: 0.5 });
  await badge();
}
async function menus() {
  await chrome.contextMenus.removeAll();
  if ((await config()).enabled)
    for (const field of ['headline', 'body_text']) {
      chrome.contextMenus.create({
        id: field,
        title: `BanglaFactGuard: use as ${field === 'headline' ? 'headline' : 'body text'}`,
        contexts: ['selection'],
        documentUrlPatterns: ['http://*/*', 'https://*/*'],
      });
    }
}
async function deliver(item) {
  const cfg = await config();
  if (
    !cfg.enabled ||
    item.owner !== ownerOf(await auth()) ||
    !item.summary?.stage ||
    item.notified === item.summary.stage
  )
    return;
  item.unread = true;
  if (cfg.notifications && (await chrome.notifications.getPermissionLevel()) === 'granted') {
    try {
      await chrome.notifications.create(`bfg:${item.id}`, {
        type: 'basic',
        iconUrl: chrome.runtime.getURL('icon.png'),
        title:
          item.summary.stage === 'failed'
            ? 'Verification could not finish'
            : item.summary.final
              ? 'Final decision ready'
              : 'Preliminary result ready',
        message: headlinePreview(item.summary.headline || item.headline) || 'Your submitted claim',
        priority: 1,
      });
    } catch {
      // A desktop-notification failure must not hide a saved result or its badge.
      item.notificationError = 'Desktop alert unavailable. Your result is saved in Activity.';
      return;
    }
  }
  item.notified = item.summary.stage;
  item.notificationError = null;
}
/** The submission no longer exists on the server: drop every local trace of
 *  it (summary, unread badge, desktop alert) so a deleted result is never shown. */
async function forget(item) {
  await chrome.storage.local.remove(ITEM + item.id);
  await chrome.notifications.clear(`bfg:${item.id}`).catch(() => {});
}
async function pollNow(force = false) {
  if (polling) return polling;
  polling = (async () => {
    if (!(await config()).enabled) return;
    for (const item of await items()) {
      if (!(await config()).enabled) break;
      if (terminal(item.status) && item.summary?.stage && item.notified !== item.summary.stage) {
        await deliver(item);
        await chrome.storage.local.set({ [ITEM + item.id]: item });
      }
      // Finished items are still re-checked (less often): a submission deleted
      // on the server must disappear here too, never linger as a cached result.
      if (!force && item.next > Date.now()) continue;
      try {
        const options = { anonymous: item.owner === 'guest' };
        let data, lookup;
        if (item.type === 'SOURCE_BASED')
          data = await request(`/verify/${item.id}/status`, options);
        else if (item.type === 'PHOTO_CARD') data = await request(`/photocard/${item.id}`, options);
        else {
          lookup = await request(`/submissions/${item.id}`, options);
          data = ready(lookup.status)
            ? await request(`/multimodal/by-submission/${item.id}`, options)
            : lookup;
        }
        item.summary = summarize(item.type, data, lookup);
        item.status = item.summary.status;
        item.headline = item.summary.headline || item.headline;
        item.error = null;
        item.failures = 0;
        item.next = Date.now() + recheckDelay(item.status);
        await deliver(item);
      } catch (e) {
        if (isDeletedOnServer(e, item.id)) {
          await forget(item);
          continue;
        }
        item.error = e.message;
        item.failures = (item.failures || 0) + 1;
        item.next = Date.now() + Math.min(300000, 30000 * 2 ** Math.min(item.failures, 4));
      }
      await chrome.storage.local.set({ [ITEM + item.id]: item });
    }
    await badge();
  })().finally(() => {
    polling = null;
  });
  return polling;
}
async function submit(draft) {
  await requireOn();
  if (submitting) throw Error('A submission is already being sent.');
  submitting = true;
  const owner = ownerOf(await auth());
  try {
    const stored = await imageStore(owner);
    const image = stored?.current;
    validateDraft(draft, image);
    await chrome.storage.local.set({
      [`sending:${owner}`]: { at: Date.now(), headline: draft.headline },
    });
    let result;
    if (draft.type === 'SOURCE_BASED') {
      result = await request('/verify/async', {
        method: 'POST',
        body: {
          headline: draft.headline.trim(),
          body_text: draft.body_text.trim() || null,
          // Optional: without an outlet the server searches the verified sources.
          claimed_source_text: draft.claimed_source_text.trim() || null,
          published_date: draft.published_date || null,
        },
      });
    } else {
      const form = new FormData();
      form.append('image', image, stored.name || 'capture.png');
      if (draft.type === 'MULTIMODAL') {
        form.append('headline', draft.headline.trim());
        form.append('body_text', draft.body_text.trim());
      }
      result = await request(
        draft.type === 'MULTIMODAL' ? '/multimodal/predict/async' : '/photocard/verify/async',
        { method: 'POST', body: form },
      );
    }
    const item = {
      id: result.submission_id,
      owner,
      type: draft.type,
      headline: draft.headline || 'Photo card',
      created: Date.now(),
      status: result.status,
      next: 0,
      unread: false,
    };
    await chrome.storage.local.set({ [ITEM + item.id]: item });
    await chrome.storage.local.remove([`draft:${owner}`, `sending:${owner}`]);
    await imageStore(owner, null);
    void pollNow().catch(() => {});
    return item;
  } finally {
    submitting = false;
  }
}
async function activeTab(windowId) {
  const query = Number.isInteger(windowId)
    ? { active: true, windowId }
    : { active: true, lastFocusedWindow: true };
  const [tab] = await chrome.tabs.query(query);
  if (!Number.isInteger(tab?.id))
    throw Error('No active page was found in this window. Open the page you want to capture.');
  // Chrome may omit url when activeTab has not been granted. Missing metadata
  // is not evidence that a normal Facebook/news page is a restricted page.
  if (tab.url && !/^https?:/.test(tab.url))
    throw Error(
      'This Chrome or extension page cannot be selected. Switch to the ' +
        'website, then click the BanglaFactGuard toolbar icon.',
    );
  return tab;
}
async function pageScript(tab, func) {
  try {
    return await chrome.scripting.executeScript({ target: { tabId: tab.id }, func });
  } catch (error) {
    if (/cannot access|permission|not allowed|extensions gallery/i.test(error.message)) {
      throw Error(
        'Chrome has not allowed access to this page. Keep the website tab active ' +
          'and click the pinned BanglaFactGuard icon in the Chrome toolbar, then ' +
          'try again. Opening only the side panel does not grant page access.',
      );
    }
    throw error;
  }
}
async function capture(windowId) {
  await requireOn();
  const owner = ownerOf(await auth());
  const api = (await config()).api;
  const tab = await activeTab(windowId);
  const [{ result, documentId }] = await pageScript(tab, selectArea);
  if (!result) return { cancelled: true };
  await requireOn();
  const current = await activeTab(tab.windowId);
  if (current.id !== tab.id || (current.url && tab.url && current.url !== tab.url))
    throw Error('The active page changed. Please select the screenshot area again.');
  const [currentDocument] = await pageScript(current, () => true);
  if (documentId && currentDocument.documentId !== documentId)
    throw Error('The page reloaded. Please select the screenshot area again.');
  const data = await chrome.tabs.captureVisibleTab(tab.windowId, { format: 'png' });
  const bitmap = await createImageBitmap(await (await fetch(data)).blob());
  const r = cropRect(result.rect, result.view, bitmap);
  const canvas = new OffscreenCanvas(r.width, r.height);
  canvas.getContext('2d').drawImage(bitmap, r.x, r.y, r.width, r.height, 0, 0, r.width, r.height);
  bitmap.close();
  const blob = await canvas.convertToBlob({ type: 'image/png' });
  await requireOn();
  if (owner !== ownerOf(await auth()) || api !== (await config()).api)
    throw Error('The account or connection changed. Please capture again.');
  await imageStore(owner, {
    original: blob,
    current: blob,
    name: 'screenshot.png',
    originalName: 'screenshot.png',
  });
  return { captured: true };
}
async function handle(message) {
  switch (message.type) {
    case 'state':
      return {
        settings: await config(),
        user: (await auth())?.user,
        items: await items(),
        busy: submitting,
        notificationPermission: await chrome.notifications.getPermissionLevel(),
      };
    case 'submit':
      if (message.owner !== ownerOf(await auth()))
        throw Error('Your account changed. Review the claim before submitting again.');
      return submit(message.draft);
    case 'poll':
      await pollNow(Boolean(message.force));
      return true;
    case 'capture':
      return capture(message.windowId);
    case 'selection': {
      await requireOn();
      const tab = await activeTab(message.windowId);
      const [{ result }] = await pageScript(tab, () => window.getSelection()?.toString() || '');
      if (!result)
        throw Error('Select some text on the page first, or paste/type into this field.');
      return result;
    }
    case 'sources':
      await requireOn();
      return request('/sources?size=100', { anonymous: true });
    case 'login': {
      await requireOn();
      if (submitting) throw Error('Wait for submission acceptance before changing accounts.');
      if (polling) await polling;
      const tokens = await request('/auth/login', {
        method: 'POST',
        body: message.credentials,
        anonymous: true,
      });
      const cfg = await config();
      const res = await fetch(cfg.api + '/auth/me', {
        headers: { Authorization: `Bearer ${tokens.access_token}` },
        signal: AbortSignal.timeout(15000),
      });
      if (!res.ok) throw Error('Could not load your account. Please try signing in again.');
      await chrome.storage.local.set({ auth: { ...tokens, user: await res.json() } });
      await badge();
      return true;
    }
    case 'logout': {
      if (submitting) throw Error('Wait for submission acceptance before signing out.');
      if (polling) await polling;
      const session = await auth();
      if (session)
        await request('/auth/logout', {
          method: 'POST',
          body: { refresh_token: session.refresh_token },
        }).catch(() => {});
      await chrome.storage.local.remove('auth');
      for (const id of Object.keys(await chrome.notifications.getAll()))
        if (id.startsWith('bfg:')) await chrome.notifications.clear(id);
      await badge();
      return true;
    }
    case 'settings': {
      if (submitting) throw Error('Wait for submission acceptance before changing settings.');
      if (polling) await polling;
      const changesConnection = ['api', 'website'].some((key) =>
        Object.hasOwn(message.settings || {}, key),
      );
      if (changesConnection) {
        const session = await auth();
        if (session?.user?.role !== 'admin')
          throw Error('Only an administrator can change connection settings.');
        // Revalidate against the current server before changing the API destination.
        const user = await request('/auth/me');
        if (user.role !== 'admin' || user.id !== session.user.id)
          throw Error('Only an administrator can change connection settings.');
      }
      const previous = await config();
      const next = { ...previous, ...message.settings };
      for (const key of ['api', 'website']) {
        const url = new URL(next[key]);
        if (
          url.username ||
          url.password ||
          url.search ||
          url.hash ||
          !(
            url.protocol === 'https:' ||
            (url.protocol === 'http:' && ['localhost', '127.0.0.1'].includes(url.hostname))
          )
        )
          throw Error(
            'Use HTTPS, or HTTP on localhost. URLs cannot contain credentials, ' +
              'queries or fragments.',
          );
        next[key] = next[key].replace(/\/+$/, '');
      }
      if (!(await chrome.permissions.contains({ origins: [new URL(next.api).origin + '/*'] })))
        throw Error('API host permission is required. Save the address again and allow access.');
      if (next.api !== previous.api) {
        const all = await chrome.storage.local.get(null);
        for (const key of Object.keys(all))
          if (key.startsWith('draft:') || key.startsWith('sending:'))
            await imageStore(key.split(':')[1], null);
        await chrome.storage.local.clear();
      }
      await chrome.storage.local.set({ settings: next });
      await menus();
      await badge();
      if (next.enabled) void pollNow(true).catch(() => {});
      return true;
    }
    case 'read': {
      if (polling) await polling;
      const item = await read(ITEM + message.id);
      if (item?.owner === ownerOf(await auth()))
        await chrome.storage.local.set({ [ITEM + item.id]: { ...item, unread: false } });
      await badge();
      return true;
    }
    case 'details': {
      const item = await read(ITEM + message.id);
      if (item?.owner !== ownerOf(await auth()))
        throw Error('Sign into the account that submitted this claim.');
      return chrome.tabs.create({
        url: (await config()).website + '/verify/' + encodeURIComponent(item.id),
      });
    }
    default:
      throw Error('Unknown extension action.');
  }
}
chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (
    sender.id !== chrome.runtime.id ||
    !sender.url?.startsWith(chrome.runtime.getURL('index.html'))
  )
    return;
  if (message.type === 'submit' && submissionQueued) {
    reply({ error: 'A submission is already being sent. Please wait for acceptance.' });
    return;
  }
  if (message.type === 'submit') submissionQueued = true;
  const work = ['state', 'capture', 'selection', 'sources'].includes(message.type)
    ? handle(message)
    : exclusive(() => handle(message));
  work
    .then(
      (data) => reply({ data }),
      (e) => reply({ error: e.message }),
    )
    .finally(() => {
      if (message.type === 'submit') submissionQueued = false;
    });
  return true;
});
chrome.action.onClicked.addListener((tab) => {
  // Call synchronously from the toolbar gesture, before any storage awaits.
  if (Number.isInteger(tab.windowId))
    void chrome.sidePanel.open({ windowId: tab.windowId }).catch(() => {});
});
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (!['headline', 'body_text'].includes(info.menuItemId)) return;
  // Invoke open synchronously from the user gesture, before storage awaits.
  const opening = chrome.sidePanel.open({ windowId: tab.windowId }).catch(() => {});
  void (async () => {
    await requireOn();
    await opening;
    await chrome.storage.local.set({
      selection: {
        field: info.menuItemId,
        text: info.selectionText,
        owner: ownerOf(await auth()),
        time: Date.now(),
      },
    });
  })().catch(() => {});
});
chrome.notifications.onClicked.addListener((id) => {
  if (id.startsWith('bfg:'))
    void chrome.tabs.create({ url: chrome.runtime.getURL('index.html') + '#activity' });
});
chrome.runtime.onInstalled.addListener(() => {
  void setup();
  void menus();
});
chrome.runtime.onStartup.addListener(() => {
  void setup()
    .then(() => exclusive(() => pollNow(true)))
    .catch(() => {});
});
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'check-results') void exclusive(() => pollNow()).catch(() => {});
});
void setup().catch(() => {});
