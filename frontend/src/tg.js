export const tg = typeof window !== "undefined" ? window.Telegram?.WebApp : undefined;
export const inTelegram = !!(tg && tg.initData);

export function setupTelegram() {
  if (!inTelegram) return;
  try {
    tg.ready(); tg.expand();
    document.documentElement.classList.add("in-tg");     // our in-app Back buttons give way to Telegram's
    tg.setHeaderColor?.("#0A0A0C"); tg.setBackgroundColor?.("#0A0A0C"); tg.setBottomBarColor?.("#0E0E11");
    tg.disableVerticalSwipes?.();
  } catch {}
}

export function haptic(kind = "light") {
  try {
    const h = tg?.HapticFeedback;
    if (!h) return navigator.vibrate?.(kind === "success" ? [10, 40, 10] : 8);
    if (kind === "success" || kind === "error" || kind === "warning") h.notificationOccurred(kind);
    else if (kind === "select") h.selectionChanged();
    else h.impactOccurred(kind);
  } catch {}
}

export function openLink(url) {
  if (inTelegram && url.startsWith("https://t.me/")) tg.openTelegramLink(url);
  else window.open(url, "_blank", "noopener");
}


/* Telegram's Back button closes the topmost sheet first, then goes to the parent screen. */
export const backStack = [];
export function pushBack(fn) { backStack.push(fn); window.dispatchEvent(new Event("nova:backstack")); }
export function popBack(fn) { const i = backStack.lastIndexOf(fn); if (i >= 0) backStack.splice(i, 1); window.dispatchEvent(new Event("nova:backstack")); }
