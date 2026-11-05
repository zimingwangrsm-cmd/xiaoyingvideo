import { mkdir, copyFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const root = fileURLToPath(new URL('.', import.meta.url));
for (const name of ['app.js', 'views.js', 'model.js']) {
  execFileSync(process.execPath, ['--check', join(root, 'src', name)], { stdio: 'inherit' });
}
await mkdir(join(root, 'dist', 'assets'), { recursive: true });
await copyFile(join(root, 'index.html'), join(root, 'dist', 'index.html'));
for (const name of ['app.js', 'views.js', 'model.js', 'styles.css']) {
  await copyFile(join(root, 'src', name), join(root, 'dist', 'assets', name));
}
console.log('Built frontend/dist (native ES modules; no downloaded dependencies).');
