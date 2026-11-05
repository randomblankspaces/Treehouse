// One HTML entry (the API server falls back to index.html); each interface loads its own code and CSS.
if (location.pathname === '/dev' || location.pathname.startsWith('/dev/')) void import('./shell/dev.tsx');
else void import('./main.tsx');
