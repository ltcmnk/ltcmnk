/**
 * Run once to get your Spotify refresh token.
 *
 * Steps:
 *   1. Create a Spotify app at https://developer.spotify.com/dashboard
 *   2. Add  https://example.com  as the Redirect URI
 *   3. Export your credentials:
 *        export SPOTIFY_CLIENT_ID="..."
 *        export SPOTIFY_CLIENT_SECRET="..."
 *   4. Run:  node get-refresh-token.js
 *   5. Open the printed URL in your browser and authorise
 *   6. You'll be redirected to example.com — copy the full URL from the address bar
 *   7. Paste it here when prompted
 *   8. Your refresh token will be printed — save it to Vercel env vars
 */

import readline from "readline";
import { execSync } from "child_process";

const CLIENT_ID = process.env.SPOTIFY_CLIENT_ID;
const CLIENT_SECRET = process.env.SPOTIFY_CLIENT_SECRET;
const REDIRECT_URI = "https://example.com";
const SCOPES = "user-read-currently-playing user-read-recently-played";

if (!CLIENT_ID || !CLIENT_SECRET) {
  console.error("\nError: set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET before running.\n");
  process.exit(1);
}

const authUrl =
  "https://accounts.spotify.com/authorize?" +
  new URLSearchParams({
    client_id: CLIENT_ID,
    response_type: "code",
    redirect_uri: REDIRECT_URI,
    scope: SCOPES,
  });

console.log("\n1. Open this URL in your browser:\n");
console.log("   " + authUrl);
console.log("\n2. Authorise the app.");
console.log("3. You'll land on example.com — copy the FULL URL from the address bar.\n");

try {
  execSync(`open "${authUrl}"`);
} catch {
  // non-mac, user opens manually
}

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

rl.question("Paste the full redirect URL here: ", async (redirected) => {
  rl.close();

  let code;
  try {
    code = new URL(redirected).searchParams.get("code");
  } catch {
    console.error("\nInvalid URL. Make sure you copied the full address bar URL.\n");
    process.exit(1);
  }

  if (!code) {
    console.error("\nNo code found in the URL.\n");
    process.exit(1);
  }

  const creds = Buffer.from(`${CLIENT_ID}:${CLIENT_SECRET}`).toString("base64");
  const res = await fetch("https://accounts.spotify.com/api/token", {
    method: "POST",
    headers: {
      Authorization: `Basic ${creds}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code,
      redirect_uri: REDIRECT_URI,
    }),
  });

  const tokens = await res.json();

  if (tokens.refresh_token) {
    console.log("\n✓ Your refresh token:\n");
    console.log("   " + tokens.refresh_token);
    console.log("\nAdd this as SPOTIFY_REFRESH_TOKEN in your Vercel project settings.\n");
  } else {
    console.error("\nFailed to get token:", JSON.stringify(tokens, null, 2));
  }
});
