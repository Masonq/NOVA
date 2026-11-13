const P = {
  plus: <><path d="M12 5v14" /><path d="M5 12h14" /></>,
  send: <><path d="M12 19V5" /><path d="M5 12l7-7 7 7" /></>,
  wave: <><path d="M4 10v4" /><path d="M8 7v10" /><path d="M12 4v16" /><path d="M16 7v10" /><path d="M20 10v4" /></>,
  image: <><rect x="3" y="5" width="18" height="14" rx="3" /><circle cx="8.5" cy="9.5" r="1.5" /><path d="M21 15l-5-5L5 21" /></>,
  video: <><rect x="3" y="6" width="13" height="12" rx="3" /><path d="M16 10l5-3v10l-5-3" /></>,
  music: <><path d="M9 17V5l10-2v12" /><circle cx="6.5" cy="17" r="2.5" /><circle cx="16.5" cy="15" r="2.5" /></>,
  home: <><path d="M3 11l9-8 9 8" /><path d="M5 10v10h14V10" /></>,
  clock: <><circle cx="12" cy="12" r="8" /><path d="M12 8v4l3 2" /></>,
  user: <><circle cx="12" cy="8" r="4" /><path d="M4 20c1.5-3.5 4.5-5 8-5s6.5 1.5 8 5" /></>,
  back: <path d="M15 6l-6 6 6 6" />,
  x: <><path d="M6 6l12 12" /><path d="M18 6L6 18" /></>,
  trash: <><path d="M4 7h16" /><path d="M9 7V4h6v3" /><path d="M6 7l1 13h10l1-13" /></>,
  download: <><path d="M12 3v12" /><path d="M7 10l5 5 5-5" /><path d="M5 21h14" /></>,
  spark: <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />,
  chevron: <path d="M9 6l6 6-6 6" />,
  heart: <path d="M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.5-7 10-7 10z" />,
  share: <><path d="M12 15V3" /><path d="M7 8l5-5 5 5" /><path d="M5 13v7h14v-7" /></>,
  play: <path d="M8 5v14l11-7z" fill="currentColor" stroke="none" />,
  pause: <><rect x="6" y="5" width="4" height="14" rx="1.5" fill="currentColor" stroke="none" /><rect x="14" y="5" width="4" height="14" rx="1.5" fill="currentColor" stroke="none" /></>,
  clip: <path d="M21 11l-8.5 8.5a5 5 0 0 1-7-7L14 4a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L15 7" />,
  check: <path d="M5 12l5 5 9-10" />,
  more: <><circle cx="5" cy="12" r="1.6" fill="currentColor" /><circle cx="12" cy="12" r="1.6" fill="currentColor" /><circle cx="19" cy="12" r="1.6" fill="currentColor" /></>,
  expand: <><path d="M14 4h6v6" /><path d="M10 20H4v-6" /><path d="M20 4l-7 7" /><path d="M4 20l7-7" /></>,
  logout: <><path d="M15 4h4v16h-4" /><path d="M10 8l-4 4 4 4" /><path d="M6 12h10" /></>,
};
export default function Icon({ n, s = 18, w = 1.8 }) {
  if (n === "agent") return (
    <svg aria-hidden="true" width={s + 2} height={s + 2} viewBox="0 0 26 26" fill="none">
      <circle cx="13" cy="13" r="10.5" stroke="currentColor" strokeWidth="1.3" opacity="0.5" />
      <circle cx="13" cy="13" r="6" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="13" cy="13" r="2.4" fill="currentColor" />
    </svg>);
  return (
    <svg aria-hidden="true" width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={w} strokeLinecap="round" strokeLinejoin="round">{P[n]}</svg>);
}
