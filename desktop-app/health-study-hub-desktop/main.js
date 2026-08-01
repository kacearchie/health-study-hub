// main.js - Desktop App with Offline Support
const { app, BrowserWindow, Menu, ipcMain, shell, dialog, Tray } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn } = require('child_process');

let mainWindow;
let flaskProcess = null;
let serverUrl = '';

// ============================================================
// GET LOCAL IP ADDRESS
// ============================================================
function getLocalIP() {
    const interfaces = os.networkInterfaces();
    for (const name of Object.keys(interfaces)) {
        for (const iface of interfaces[name]) {
            if (iface.family === 'IPv4' && !iface.internal) {
                return iface.address;
            }
        }
    }
    return '127.0.0.1';
}

// ============================================================
// CHECK OFFLINE CONTENT
// ============================================================
function hasOfflineContent() {
    const offlinePath = path.join(app.getPath('userData'), 'offline-content.json');
    try {
        if (fs.existsSync(offlinePath)) {
            const data = JSON.parse(fs.readFileSync(offlinePath, 'utf-8'));
            return data && data.notes && Object.keys(data.notes).length > 0;
        }
    } catch (e) {}
    return false;
}

function getOfflineContent() {
    const offlinePath = path.join(app.getPath('userData'), 'offline-content.json');
    try {
        if (fs.existsSync(offlinePath)) {
            return JSON.parse(fs.readFileSync(offlinePath, 'utf-8'));
        }
    } catch (e) {}
    return null;
}

// ============================================================
// CREATE WINDOW
// ============================================================
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        minWidth: 800,
        minHeight: 600,
        icon: path.join(__dirname, '../static/icons/icon-512x512.png'),
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
        },
        titleBarStyle: 'default',
        show: false,
    });

    // Menu
    const template = [
        {
            label: 'File',
            submenu: [
                {
                    label: 'Download Offline Content',
                    accelerator: 'CmdOrCtrl+D',
                    click: () => { downloadOfflineContent(); }
                },
                { type: 'separator' },
                { label: 'Reload', accelerator: 'CmdOrCtrl+R', click: () => { mainWindow.reload(); } },
                { label: 'Toggle Dev Tools', accelerator: 'CmdOrCtrl+Shift+I', click: () => { mainWindow.webContents.toggleDevTools(); } },
                { type: 'separator' },
                { label: 'Exit', accelerator: 'CmdOrCtrl+Q', click: () => { app.quit(); } }
            ]
        },
        {
            label: 'View',
            submenu: [
                { role: 'resetZoom' },
                { role: 'zoomIn' },
                { role: 'zoomOut' },
                { type: 'separator' },
                { role: 'togglefullscreen' }
            ]
        },
        {
            label: 'Help',
            submenu: [
                {
                    label: 'Health Study Hub Website',
                    click: () => { shell.openExternal('https://health-study-hub.onrender.com'); }
                },
                {
                    label: 'About',
                    click: () => {
                        dialog.showMessageBox(mainWindow, {
                            type: 'info',
                            title: 'Health Study Hub',
                            message: 'Health Study Hub v1.0.0',
                            detail: 'Pharmaceutical & Health Sciences Study Platform\nMUST / UG\n\nOffline Mode: ' + (hasOfflineContent() ? '✅ Available' : '❌ Not Available'),
                            buttons: ['OK']
                        });
                    }
                }
            ]
        }
    ];

    const menu = Menu.buildFromTemplate(template);
    Menu.setApplicationMenu(menu);

    // Try to connect to server
    const localIP = getLocalIP();
    const urls = [
        `http://${localIP}:5000`,
        'http://127.0.0.1:5000',
        'https://health-study-hub.onrender.com'
    ];

    // Start Flask server
    startFlaskServer();

    // Try to connect
    tryConnect(urls, 0);
}

// ============================================================
// START FLASK SERVER
// ============================================================
function startFlaskServer() {
    const appPath = path.join(__dirname, '..', 'app.py');
    
    if (fs.existsSync(appPath)) {
        const python = process.platform === 'win32' ? 'python' : 'python3';
        flaskProcess = spawn(python, [appPath], {
            cwd: path.join(__dirname, '..'),
            stdio: 'pipe'
        });

        flaskProcess.stdout.on('data', (data) => {
            console.log(`[Flask] ${data}`);
            if (data.toString().includes('Running on')) {
                // Server started
            }
        });

        flaskProcess.stderr.on('data', (data) => {
            console.error(`[Flask Error] ${data}`);
        });

        flaskProcess.on('close', () => {
            console.log('Flask server closed');
        });
    }
}

// ============================================================
// TRY CONNECT TO SERVER
// ============================================================
function tryConnect(urls, index) {
    if (index >= urls.length) {
        showOfflinePage();
        return;
    }

    const url = urls[index];
    const { exec } = require('child_process');
    
    exec(`curl -s -o /dev/null -w "%{http_code}" ${url}/health`, (error, stdout) => {
        if (!error && stdout.trim() === '200') {
            serverUrl = url;
            mainWindow.loadURL(url);
            mainWindow.show();
            // mainWindow.webContents.openDevTools();
            mainWindow.webContents.on('did-finish-load', () => {
                mainWindow.webContents.executeJavaScript(`
                    if (window.downloadOfflineContent) {
                        window.downloadOfflineContent();
                    }
                `);
            });
        } else {
            tryConnect(urls, index + 1);
        }
    });
}

// ============================================================
// SHOW OFFLINE PAGE
// ============================================================
function showOfflinePage() {
    const offlineContent = getOfflineContent();
    const hasContent = offlineContent && offlineContent.notes && Object.keys(offlineContent.notes).length > 0;

    if (hasContent) {
        mainWindow.loadFile('offline-reader.html');
        mainWindow.show();
    } else {
        mainWindow.loadFile('offline.html');
        mainWindow.show();
    }
}

// ============================================================
// DOWNLOAD OFFLINE CONTENT
// ============================================================
function downloadOfflineContent() {
    mainWindow.webContents.executeJavaScript(`
        fetch('/api/offline/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: 'guest' })
        })
        .then(r => r.json())
        .then(data => {
            localStorage.setItem('offlineData', JSON.stringify(data));
            return data;
        })
    `).then((data) => {
        if (data) {
            const offlinePath = path.join(app.getPath('userData'), 'offline-content.json');
            fs.writeFileSync(offlinePath, JSON.stringify(data, null, 2));
            dialog.showMessageBox(mainWindow, {
                type: 'info',
                title: 'Download Complete',
                message: 'Offline content downloaded successfully!',
                detail: `Downloaded ${Object.keys(data.notes || {}).length} notes and ${Object.keys(data.quizzes || {}).length} quizzes.`,
                buttons: ['OK']
            });
        }
    }).catch((error) => {
        dialog.showMessageBox(mainWindow, {
            type: 'error',
            title: 'Download Failed',
            message: 'Failed to download offline content.',
            detail: error.message,
            buttons: ['OK']
        });
    });
}

// ============================================================
// IPC HANDLERS
// ============================================================
ipcMain.handle('download-offline', downloadOfflineContent);
ipcMain.handle('has-offline-content', () => hasOfflineContent());

// ============================================================
// APP LIFECYCLE
// ============================================================
app.whenReady().then(() => {
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        if (flaskProcess) flaskProcess.kill();
        app.quit();
    }
});

app.on('before-quit', () => {
    if (flaskProcess) flaskProcess.kill();
});