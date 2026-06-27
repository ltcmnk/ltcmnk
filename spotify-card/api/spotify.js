import sharp from "sharp";

const {
  SPOTIFY_CLIENT_ID,
  SPOTIFY_CLIENT_SECRET,
  SPOTIFY_REFRESH_TOKEN,
} = process.env;

const THEMES = {
  dark: {
    bg: "#0D1117",
    text: "#F0F3F6",
    key: "#8B949E",
    soft: "#6E7681",
    playing: "#3FB950",
  },
  light: {
    bg: "#F6F8FA",
    text: "#24292F",
    key: "#6E7781",
    soft: "#8C959F",
    playing: "#1A7F37",
  },
};

const ASCII_CHARS = " ░▒▓█";

async function getAccessToken() {
  const creds = Buffer.from(`${SPOTIFY_CLIENT_ID}:${SPOTIFY_CLIENT_SECRET}`).toString("base64");
  const res = await fetch("https://accounts.spotify.com/api/token", {
    method: "POST",
    headers: {
      Authorization: `Basic ${creds}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({ grant_type: "refresh_token", refresh_token: SPOTIFY_REFRESH_TOKEN }),
  });
  const data = await res.json();
  return data.access_token;
}

async function getNowPlaying(token) {
  const res = await fetch("https://api.spotify.com/v1/me/player/currently-playing", {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (res.status === 204) return null;

  const data = await res.json();
  if (!data?.item) return null;

  return {
    isPlaying: data.is_playing,
    name: data.item.name,
    artist: data.item.artists.map((a) => a.name).join(", "),
    album: data.item.album.name,
    artUrl: data.item.album.images.find((i) => i.width <= 300)?.url ?? data.item.album.images[0]?.url,
  };
}

async function getLastPlayed(token) {
  const res = await fetch("https://api.spotify.com/v1/me/player/recently-played?limit=1", {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json();
  const item = data?.items?.[0];
  if (!item) return null;

  return {
    isPlaying: false,
    name: item.track.name,
    artist: item.track.artists.map((a) => a.name).join(", "),
    album: item.track.album.name,
    artUrl: item.track.album.images.find((i) => i.width <= 300)?.url ?? item.track.album.images[0]?.url,
  };
}

async function albumToAscii(artUrl) {
  try {
    const res = await fetch(artUrl);
    const buf = Buffer.from(await res.arrayBuffer());

    const { data, info } = await sharp(buf)
      .resize(8, 5, { fit: "fill" })
      .raw()
      .toBuffer({ resolveWithObject: true });

    const rows = [];
    for (let y = 0; y < 5; y++) {
      let row = "";
      for (let x = 0; x < 8; x++) {
        const idx = (y * 8 + x) * info.channels;
        const r = data[idx], g = data[idx + 1], b = data[idx + 2];
        const lum = 0.299 * r + 0.587 * g + 0.114 * b;
        row += ASCII_CHARS[Math.min(Math.floor((lum / 256) * ASCII_CHARS.length), ASCII_CHARS.length - 1)];
      }
      rows.push(row);
    }
    return rows;
  } catch {
    return ["        ", " ░▒▓▒░  ", " ▒████▒ ", " ░▒▓▒░  ", "        "];
  }
}

function esc(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function trunc(str, max) {
  return str.length > max ? str.slice(0, max - 1) + "…" : str;
}

function dots(prefixLen, valueLen, col = 38) {
  const n = col - prefixLen - valueLen;
  if (n <= 2) return n === 1 ? " " : "";
  return " " + ".".repeat(n - 2) + " ";
}

function buildSvg(track, ascii, theme) {
  const c = THEMES[theme] ?? THEMES.dark;

  const statusLabel = track.isPlaying ? "playing" : "last played";
  const trackName = esc(trunc(track.name, 28));
  const artistName = esc(trunc(track.artist, 28));
  const albumName = esc(trunc(track.album, 28));

  const statusDots = dots(". Status:".length, statusLabel.length);
  const trackDots = dots(". Track:".length, track.name.length > 28 ? 29 : track.name.length);
  const artistDots = dots(". Artist:".length, track.artist.length > 28 ? 29 : track.artist.length);
  const albumDots = dots(". Album:".length, track.album.length > 28 ? 29 : track.album.length);

  const artX = 15;
  const infoX = 110;

  return `<?xml version='1.0' encoding='UTF-8'?>
<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback, Consolas, monospace" width="985px" height="185px" font-size="16px">
  <style>
    @font-face {
      src: local('Consolas'), local('Consolas Bold');
      font-family: 'ConsolasFallback';
      font-display: swap;
      -webkit-size-adjust: 109%;
      size-adjust: 109%;
    }
    text, tspan { white-space: pre; }
  </style>

  <rect width="985px" height="185px" fill="${c.bg}" rx="15"/>

  <text x="${artX}" y="50" fill="${c.text}">
    ${ascii.map((row, i) => `<tspan x="${artX}" y="${50 + i * 20}">${esc(row)}</tspan>`).join("\n    ")}
  </text>

  <text x="${infoX}" y="30" fill="${c.text}">
    <tspan x="${infoX}" y="30">mishka@spotify</tspan><tspan fill="${c.soft}"> -——————————————————————————————————————————</tspan>

    <tspan x="${infoX}" y="50" fill="${c.soft}">. </tspan><tspan fill="${c.key}">Status</tspan>:<tspan fill="${c.soft}">${statusDots}</tspan><tspan fill="${track.isPlaying ? c.playing : c.soft}">${statusLabel}</tspan>
    <tspan x="${infoX}" y="70" fill="${c.soft}">. </tspan><tspan fill="${c.key}">Track</tspan>:<tspan fill="${c.soft}">${trackDots}</tspan><tspan fill="${c.text}">${trackName}</tspan>
    <tspan x="${infoX}" y="90" fill="${c.soft}">. </tspan><tspan fill="${c.key}">Artist</tspan>:<tspan fill="${c.soft}">${artistDots}</tspan><tspan fill="${c.text}">${artistName}</tspan>
    <tspan x="${infoX}" y="110" fill="${c.soft}">. </tspan><tspan fill="${c.key}">Album</tspan>:<tspan fill="${c.soft}">${albumDots}</tspan><tspan fill="${c.text}">${albumName}</tspan>
  </text>
</svg>`;
}

export default async function handler(req, res) {
  const theme = req.query?.theme === "light" ? "light" : "dark";

  try {
    const token = await getAccessToken();
    const track = (await getNowPlaying(token)) ?? (await getLastPlayed(token));

    if (!track) {
      const svg = buildSvg(
        { isPlaying: false, name: "—", artist: "—", album: "—" },
        ["        ", "        ", "  ░▒▓░  ", "        ", "        "],
        theme
      );
      res.setHeader("Content-Type", "image/svg+xml");
      res.setHeader("Cache-Control", "public, max-age=60, s-maxage=60");
      return res.send(svg);
    }

    const ascii = await albumToAscii(track.artUrl);
    const svg = buildSvg(track, ascii, theme);

    res.setHeader("Content-Type", "image/svg+xml");
    res.setHeader("Cache-Control", "public, max-age=60, s-maxage=60");
    res.send(svg);
  } catch (err) {
    res.status(500).send(`<svg xmlns="http://www.w3.org/2000/svg"><text y="20">${err.message}</text></svg>`);
  }
}
