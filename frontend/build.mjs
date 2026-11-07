import { mkdir, copyFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const distName = process.env.BUILD_DIR || 'dist';
const root = fileURLToPath(new URL('.', import.meta.url));
for (const name of ['app.js', 'views.js', 'model.js', 'v2views.js', 'drafts.js', 'dom.js', 'recorder.js']) {
  execFileSync(process.execPath, ['--check', join(root, 'src', name)], { stdio: 'inherit' });
}
await mkdir(join(root, distName, 'assets'), { recursive: true });
await copyFile(join(root, 'index.html'), join(root, distName, 'index.html'));
for (const name of ['app.js', 'views.js', 'model.js', 'v2views.js', 'drafts.js', 'dom.js', 'recorder.js', 'styles.css']) {
  await copyFile(join(root, 'src', name), join(root, distName, 'assets', name));
}
console.log('Built frontend/dist (native ES modules; no downloaded dependencies).');
