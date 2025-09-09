import path from 'path';
import fs from 'fs/promises';
import { useMultiFileAuthState, initAuthCreds, BufferJSON } from '@whiskeysockets/baileys';

// Gestor simple de estado de autenticación usando archivos en disco.
// Ubicación por defecto: <repo>/whatsapp/auth/<sessionId>
export async function useFileAuthState(sessionId = 'default') {
    const baseDir = path.join(process.cwd(), 'whatsapp', 'auth', sessionId);
    // useMultiFileAuthState crea la carpeta y archivos necesarios
    const { state, saveCreds } = await useMultiFileAuthState(baseDir);

    async function clearSession() {
        // Eliminar la carpeta de auth para forzar nuevo QR
        try {
            await fs.rm(path.join(process.cwd(), 'whatsapp', 'auth', sessionId), { recursive: true, force: true });
        } catch (e) {
            // ignore
        }
    }

    // Implementaciones mínimas para compatibilidad con la API usada en el proyecto
    async function getMessage(key) {
        // No implementado en disco; Baileys puede trabajar sin esto en muchos casos.
        return undefined;
    }

    async function saveMessage(key, message) {
        // noop - no almacenamos mensajes en archivos en esta versión
    }

    async function updateSessionStatus(status, metadata = {}) {
        // opcional: podríamos escribir un archivo status.json
        try {
            const statusDir = path.join(process.cwd(), 'whatsapp', 'auth', sessionId);
            await fs.mkdir(statusDir, { recursive: true });
            const payload = { sessionId, status, lastActive: new Date().toISOString(), ...metadata };
            await fs.writeFile(path.join(statusDir, 'status.json'), JSON.stringify(payload, null, 2), 'utf8');
        } catch (e) {
            // ignore
        }
    }

    return {
        state,
        saveCreds,
        getMessage,
        saveMessage,
        clearSession,
        updateSessionStatus
    };
}
