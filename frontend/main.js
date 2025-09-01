import 'htmx.org';
import './style.css';
import Alpine from 'alpinejs';

window.Alpine = Alpine;
Alpine.start();

console.log('Vite + Django + HTMX + Alpine + Tailwind initialized');
console.log('HTMX version:', window.htmx?.version ?? 'not found');
console.log('Alpine present:', !!window.Alpine);
