const { spawn, spawnSync } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');

function checkBackendHealth() {
  return new Promise((resolve) => {
    const req = http.get('http://127.0.0.1:8000/api/health', (res) => {
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(1000, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function main() {
  console.log('\x1b[36m%s\x1b[0m', '>> Starting TruthCart AI dev environment...');

  // Ensure frontend packages are installed
  const frontendModules = path.join(__dirname, '..', 'frontend', 'node_modules');
  if (!fs.existsSync(frontendModules)) {
    console.log('\x1b[33m%s\x1b[0m', '>> Installing frontend packages...');
    spawnSync('npm --prefix frontend install', { stdio: 'inherit', shell: true });
  }

  // Check and start backend if not running
  const isHealthy = await checkBackendHealth();
  let backendProc = null;

  if (isHealthy) {
    console.log('\x1b[32m%s\x1b[0m', '>> TruthCart Python backend is active at http://127.0.0.1:8000');
  } else {
    console.log('\x1b[33m%s\x1b[0m', '>> Launching Python backend on http://127.0.0.1:8000...');
    backendProc = spawn(
      'python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload',
      { stdio: 'inherit', shell: true }
    );

    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 500));
      if (await checkBackendHealth()) {
        console.log('\x1b[32m%s\x1b[0m', '>> TruthCart Python backend is ready!');
        break;
      }
    }
  }

  console.log('\x1b[36m%s\x1b[0m', '>> Launching Vite frontend...');
  const frontendProc = spawn('npm --prefix frontend run dev', {
    stdio: 'inherit',
    shell: true,
  });

  const cleanup = () => {
    console.log('\n>> Shutting down TruthCart services...');
    if (frontendProc) frontendProc.kill();
    if (backendProc) backendProc.kill();
    process.exit();
  };

  process.on('SIGINT', cleanup);
  process.on('SIGTERM', cleanup);
}

main().catch((err) => {
  console.error('>> Error in dev launcher:', err);
  process.exit(1);
});
