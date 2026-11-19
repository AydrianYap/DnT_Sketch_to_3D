// D&T Sketch-to-3D front-end settings.
//
// apiBase: where the AI backend lives.
//   ""  (empty) = the same computer that served this page. Use this when the page is
//                 opened from the backend itself, e.g. http://localhost:8000 or the
//                 laptop's LAN address. This is the setting for Stages 1-5.
//   "https://..." = a separate backend address, for the future Cloudflare-hosted page
//                 (Stage 6). Never put passwords or API keys in this file: it is public.
window.DNT_CONFIG = {
  apiBase: "",
};
