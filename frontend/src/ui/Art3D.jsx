import { useState } from "react";

/** Glossy 3D illustration (3dicons by Vijay Verma, CC0), served from our own server: /files/3d/<name>.webp.
 *  Hides itself if the file isn't there yet (the server downloads the set on install). */
export default function Art3D({ name, size = 96, className = "", alt = "" }) {
  const [ok, setOk] = useState(true);
  if (!ok) return null;
  return <img className={"art3d " + className} src={`/files/3d/${name}.webp`} width={size} height={size} alt={alt} aria-hidden={alt ? undefined : true}
    loading="lazy" decoding="async" draggable={false} onError={() => setOk(false)} />;
}
