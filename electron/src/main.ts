// Electron main process.
//
// Responsibilities:
//   • create the BrowserWindow (Vite dev server in dev, the bundled UI in prod)
//   • own the CLI child process lifecycle
//   • expose the CLI over IPC to the renderer
//   • refuse to start cleanly when the CLI binary is missing
//
// The renderer contains no disk logic at all — every measurement, every
// duplicate hash and every cleanup decision happens in the Python CLI.

import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import * as backend from './backend'

const isDev = process.env.DISKGOUP_ELECTRON_DEV === '1'
const DEV_RENDERER_URL = process.env.DISKGOUP_ELECTRON_RENDERER_URL || 'http://localhost:5173'

let mainWindow: BrowserWindow | null = null

// ────────────────────────────────────────────────────────────────────────────
// Single instance — two launches would spawn two CLIs.
// ────────────────────────────────────────────────────────────────────────────
if (!app.requestSingleInstanceLock()) {
  app.quit()
  process.exit(0)
}

function registerIpc(): void {
  ipcMain.handle('cli:call', async (_event, method: string, params: Record<string, unknown>) => {
    try {
      return { ok: true, result: await backend.call(method, params) }
    } catch (err) {
      return { ok: false, error: err instanceof Error ? err.message : String(err) }
    }
  })

  ipcMain.handle('cli:status', () => backend.getStatus())

  ipcMain.handle('app:info', () => ({
    version: app.getVersion(),
    platform: process.platform,
    packaged: app.isPackaged,
    cliPath: backend.resolveBinary(),
  }))

  ipcMain.handle('shell:open', async (_event, path: string) => {
    if (!existsSync(path)) return `not found: ${path}`
    const error = await shell.openPath(path)
    return error || ''
  })
}

backend.onStatus((status) => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('cli:status', status)
  }
})

backend.onNotification((notification) => {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('cli:notification', notification)
  }
})

async function createWindow(): Promise<void> {
  mainWindow = new BrowserWindow({
    width: 1360,
    height: 880,
    minWidth: 1024,
    minHeight: 640,
    title: 'DiskGOup',
    backgroundColor: '#0d1117',
    show: false,
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    webPreferences: {
      preload: join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      // The renderer is sandboxed: it loads only local assets and talks to
      // the CLI exclusively through the preload bridge.
      sandbox: true,
      spellcheck: false,
    },
  })

  mainWindow.once('ready-to-show', () => mainWindow?.show())
  mainWindow.on('closed', () => {
    mainWindow = null
  })

  if (isDev) {
    await mainWindow.loadURL(DEV_RENDERER_URL)
  } else {
    const indexPath = join(__dirname, 'renderer', 'index.html')
    if (!existsSync(indexPath)) {
      dialog.showErrorBox(
        'DiskGOup UI is missing',
        `The renderer bundle was not found at:\n${indexPath}\n\nRun "npm run build:assets" in electron/.`,
      )
      app.quit()
      return
    }
    await mainWindow.loadFile(indexPath)
  }
}

async function bootstrap(): Promise<void> {
  registerIpc()

  // The CLI binary must exist before the app can do anything useful. Say so
  // plainly instead of showing an empty window.
  if (!backend.binaryExists()) {
    const choice = await dialog.showMessageBox({
      type: 'error',
      buttons: ['Open build instructions', 'Quit'],
      defaultId: 0,
      cancelId: 1,
      title: 'DiskGOup CLI not found',
      message: 'The DiskGOup CLI binary is missing.',
      detail: backend.missingBinaryMessage(),
    })
    if (choice.response === 0) {
      await shell.openExternal('https://github.com/elshadaghazade/diskgoup-alternative#development')
    }
    app.quit()
    return
  }

  backend.start()
  await createWindow()
}

app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.focus()
  }
})

app.on('window-all-closed', () => {
  backend.stop()
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) void createWindow()
})

app.on('before-quit', () => backend.stop())

// The window can only be created once Electron is ready.
app.whenReady().then(() => bootstrap()).catch((err: unknown) => {
  console.error('[main] failed to start', err)
  app.quit()
})
