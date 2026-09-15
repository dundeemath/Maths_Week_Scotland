/* ============================================================
   GLOBAL SAFETY SWITCH for every interactive app on the website
   and in the booklet -- Analemma (Galileo/Kepler/Newton/Einstein),
   Circadian Rhythm, Leaf Curvature, Fibonacci Bees, Fractal Fern,
   Koenigsberg Bridges, Phyllotaxis, Tree Trigonometry, and the
   Travelling Salesman map.

   If an app misbehaves on phones during the exhibition, change
   ONLY the line below (true -> false) and re-upload this one file.
   Every already-published page loads it fresh on each visit, so
   nothing else needs to be rebuilt or re-uploaded. Every interactive
   app is then hidden and each page falls back to its surrounding
   plain text and images -- nothing else about the page changes.

   Flip it back to true (and re-upload again) to bring the apps back.
   ============================================================ */
window.SHOW_JS_APPS = true;

document.documentElement.setAttribute(
  "data-js-apps",
  window.SHOW_JS_APPS === false ? "off" : "on"
);
