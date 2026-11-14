import { useState } from "react";

/* NOVA's own drawn set (/files/art, made on the server) first; the free 3dicons set (/files/3d, CC0) while ours isn't
   there yet; nothing at all if neither is. */
const OWN = { gift: "gift", "money-bag": "bag", "3d-coin": "coins", trophy: "trophy", mic: "mic", "video-camera": "camera",
  "magic-trick": "wand", picture: "picture" };

export default function Art3D({ name, size = 96, className = "", alt = "" }) {
  const srcs = [OWN[name] && `/files/art/${OWN[name]}.webp`, `/files/3d/${name}.webp`].filter(Boolean);
  const [i, setI] = useState(0);
  if (i >= srcs.length) return null;
  return <img className={"art3d " + className} src={srcs[i]} width={size} height={size} alt={alt} aria-hidden={alt ? undefined : true}
    loading="lazy" decoding="async" draggable={false} onError={() => setI(i + 1)} />;
}

/** The hero picture with Walt-like life: it floats and sways slowly, small stars twinkle around it. */
const STARS = [[8, 18, 10, 0], [86, 10, 14, 0.6], [92, 52, 8, 1.3], [4, 62, 12, 0.9], [20, 88, 7, 1.8], [78, 84, 11, 0.3],
  [50, 2, 6, 2.1], [64, 30, 5, 1.1], [30, 40, 5, 2.4], [70, 66, 6, 1.6]];
export function HeroArt({ name, size = 150 }) {
  return (
    <div className="hero-art-w" style={{ width: size * 1.7, height: size * 1.25 }} aria-hidden="true">
      {STARS.map(([x, y, s, d], k) => (
        <svg key={k} className="tw" viewBox="0 0 10 10" style={{ left: `${x}%`, top: `${y}%`, width: s, height: s, animationDelay: `${d}s` }}>
          <path d="M5 0C5.6 3.4 6.6 4.4 10 5 6.6 5.6 5.6 6.6 5 10 4.4 6.6 3.4 5.6 0 5 3.4 4.4 4.4 3.4 5 0Z" fill="currentColor" />
        </svg>))}
      <div className="hero-float"><Art3D name={name} size={size} className="hero-art" /></div>
    </div>);
}
