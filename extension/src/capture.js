// Serialized by Chrome into the active page; keep this function self-contained.
export async function selectArea() {
  if (document.getElementById('__bfg_capture')) throw Error('A screenshot selection is already open.');
  return new Promise(resolve => {
    const host = document.createElement('div');
    host.id = '__bfg_capture';
    host.style.cssText = 'position:fixed;inset:0;z-index:2147483647;';
    const root = host.attachShadow({ mode: 'closed' });
    root.innerHTML = `<style>:host{all:initial} .cover{position:fixed;inset:0;cursor:crosshair;background:#102a2055;touch-action:none} .hint{position:absolute;top:15px;left:50%;transform:translateX(-50%);background:white;color:#102a20;padding:12px 18px;border-radius:12px;font:14px system-ui;pointer-events:none}.box{position:absolute;border:2px solid #1f7f4e;background:#ffffff30;pointer-events:none;display:none}</style><div class="cover"><div class="hint">Drag to select a screenshot area · Esc to cancel</div><div class="box"></div></div>`;
    document.documentElement.append(host);
    const cover = root.querySelector('.cover'), box = root.querySelector('.box');
    const previous = document.documentElement.style.overflow;
    document.documentElement.style.overflow = 'hidden';
    let start, ended = false;
    const finish = value => {
      if (ended) return;
      ended = true;
      clearTimeout(timer);
      document.removeEventListener('keydown', onKey, true);
      window.removeEventListener('resize', cancel);
      host.remove(); document.documentElement.style.overflow = previous;
      // Give the compositor time to remove the selection UI before capture.
      setTimeout(() => resolve(value), 150);
    };
    const cancel = () => finish(null);
    const onKey = e => { if (e.key === 'Escape') { e.stopImmediatePropagation(); cancel(); } };
    document.addEventListener('keydown', onKey, true);
    window.addEventListener('resize', cancel);
    const timer = setTimeout(cancel, 90000);
    cover.onpointerdown = e => {
      if (e.button !== 0) return;
      start = { x: e.clientX, y: e.clientY }; cover.setPointerCapture(e.pointerId);
    };
    cover.onpointermove = e => {
      if (!start) return;
      box.style.cssText = `display:block;left:${Math.min(start.x,e.clientX)}px;top:${Math.min(start.y,e.clientY)}px;width:${Math.abs(e.clientX-start.x)}px;height:${Math.abs(e.clientY-start.y)}px`;
    };
    cover.onpointerup = e => {
      if (!start) return;
      const rect = { x: Math.max(0,Math.min(start.x,e.clientX)), y: Math.max(0,Math.min(start.y,e.clientY)), width: Math.abs(e.clientX-start.x), height: Math.abs(e.clientY-start.y) };
      if (rect.width < 8 || rect.height < 8) { start = null; box.style.display = 'none'; return; }
      finish({ rect, view: { width: innerWidth, height: innerHeight } });
    };
    cover.onpointercancel = cancel;
  });
}
