import { useEffect, useLayoutEffect, useRef, useState } from "react";

/** Grow / fold a box as one motion: the box animates its height while the given parts glide from their old places to
 *  the new ones (FLIP — measure before and after, start from the old place with a transform, run to zero).
 *  `parts()` returns the elements to glide; offsets are taken from the box, so it must be position: relative. */
export function useFlip(boxRef, parts, deps) {
  const geo = useRef(null), timer = useRef(0);
  useLayoutEffect(() => {
    const box = boxRef.current, old = geo.current;
    if (!box || !old || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const h1 = box.offsetHeight;
    if (Math.abs(h1 - old.h) < 2) return;
    clearTimeout(timer.current);
    const ease = "cubic-bezier(.22,.9,.25,1)", dur = 320, els = parts();
    box.style.transition = "none"; box.style.height = old.h + "px"; box.style.overflow = "hidden";
    els.forEach((el, i) => {
      const o = old.pos[i]; if (!el || !o) return;
      el.style.transition = "none"; el.style.transform = `translate(${o[0] - el.offsetLeft}px, ${o[1] - el.offsetTop}px)`;
    });
    void box.offsetHeight;
    box.style.transition = `height ${dur}ms ${ease}`; box.style.height = h1 + "px";
    els.forEach((el) => { if (el) { el.style.transition = `transform ${dur}ms ${ease}`; el.style.transform = ""; } });
    timer.current = setTimeout(() => {
      box.style.transition = box.style.height = box.style.overflow = "";
      els.forEach((el) => { if (el) el.style.transition = ""; });
    }, dur + 30);
  }, deps);
  useLayoutEffect(() => {                 // where everything stands now: the start of the next change
    const box = boxRef.current; if (!box) return;
    geo.current = { h: box.style.height ? parseFloat(box.style.height) : box.offsetHeight,
      pos: parts().map((el) => (el ? [el.offsetLeft, el.offsetTop] : null)) };
  });
}

/** «Focused» for a field that should stay open until the user taps elsewhere (iOS fires stray blurs while the keyboard
 *  opens, so blur isn't trusted). */
export function useStickyFocus(boxRef) {
  const [focus, setFocus] = useState(false);
  useEffect(() => {
    if (!focus) return;
    const out = (e) => { if (!boxRef.current?.contains(e.target)) setFocus(false); };
    document.addEventListener("pointerdown", out, true);
    return () => document.removeEventListener("pointerdown", out, true);
  }, [focus]);
  return [focus, setFocus];
}
