import express from 'express';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import redis from '../config/redis.js';
import { useRedisAuthState } from '../auth_state.js';

const router = express.Router();

// Determinar __dirname en ESM
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Ruta para servir el panel principal (index.html) solo si HTTP_URL=TRUE
if (process.env.HTTP_URL === 'TRUE') {
    router.get('/', (req, res) => {
        const indexPath = path.join(__dirname, '..', 'public', 'index.html');
        if (fs.existsSync(indexPath)) {
            res.sendFile(indexPath);
        } else {
            // Intentar ruta alternativa (por si se ejecuta desde otro CWD)
            const altPath = path.join(process.cwd(), 'whatsapp', 'public', 'index.html');
            if (fs.existsSync(altPath)) {
                res.sendFile(altPath);
            } else {
                res.status(404).send('Archivo index.html no encontrado');
            }
        }
    });
}

// Ruta para exponer el QR como imagen
router.get('/qr', (req, res) => {
    const qrPath = path.join(process.cwd(), 'qr.png');
    if (fs.existsSync(qrPath)) {
        res.sendFile(qrPath);
    } else {
        res.status(404).send('QR no disponible');
        console.log('QR no disponible');
    }
});

// Ruta para iniciar sesión (forzar escaneo QR solo si no hay sesión activa)
router.get('/login', async (req, res) => {
    // Limpiar toda la sesión de Redis para forzar nueva autenticación (QR)
    try {
        const authState = await useRedisAuthState();
        await authState.clearSession();
        res.json({ success: true, message: 'Escanee el QR.' });
        setTimeout(() => process.exit(1), 200); // Dar tiempo a Express de enviar la respuesta
    } catch (e) {
        res.status(500).json({ success: false, message: 'Error al iniciar sesión.' });
    }
});

// Ruta para cerrar sesión (logout y eliminar credenciales de Redis)
router.get('/logout', async (req, res) => {
    // Cerrar sesión de Baileys si está activa y limpiar toda la sesión de Redis
    try {
        if (global.sock && typeof global.sock.logout === 'function') {
            await global.sock.logout();
        }
    } catch (e) {
        console.error('Error al cerrar sesión:', e);
        return res.status(500).json({ success: false, message: 'Error al cerrar sesión.' });
    }
    try {
        const authState = await useRedisAuthState();
        await authState.clearSession();
        res.json({ success: true, message: 'Sesión cerrada.' });
        setTimeout(() => process.exit(1), 200); // Dar tiempo a Express de enviar la respuesta
    } catch (e) {
        res.status(500).json({ success: false, message: 'Error al limpiar credenciales.' });
    }
});

// Endpoint para consultar el estado de la sesión de WhatsApp
// Endpoint para consultar el estado de la sesión de WhatsApp (realmente conectada)
router.get('/status', (req, res) => {
    if (global.isConnected) {
        res.json({ success: true, message: 'Sesion iniciada con exito' });
    } else {
        res.json({ success: false, error: 'No hay sesión activa' });
    }
});

export default router;
