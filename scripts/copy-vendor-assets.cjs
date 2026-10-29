const fs = require('node:fs');
const path = require('node:path');

const source = path.join(__dirname, '..', 'node_modules', 'dompurify', 'dist', 'purify.min.js');
const destination = path.join(__dirname, '..', 'static', 'js', 'vendor', 'purify.min.js');

fs.mkdirSync(path.dirname(destination), { recursive: true });
fs.copyFileSync(source, destination);
