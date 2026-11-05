// One HTML entry (the API server falls back to index.html); each interface loads its own code and CSS.
const path = location.pathname;
if (path === '/' || path === '/index.html') void import('./shell/story.tsx');
else if (path === '/dev' || path.startsWith('/dev/')) void import('./shell/dev.tsx');
else void import('./main.tsx');   // the earlier observatory screens (/runs, /new, /settings)
