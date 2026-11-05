// One HTML entry (the API server falls back to index.html). The observatory mounts synchronously, as before;
// the storybook (/), dev view (/dev) and pitch (/pitch) load their own code and CSS on demand.
import { mountObservatory } from './main.tsx';

const path = location.pathname;
if (path === '/' || path === '/index.html') void import('./shell/story.tsx');
else if (path === '/pitch' || path === '/pitch/') void import('./pitch/pitch.tsx');
else if (path === '/dev' || path.startsWith('/dev/')) void import('./shell/dev.tsx');
else mountObservatory();   // the earlier screens: /runs, /new, /settings
