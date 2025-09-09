/**
 * auth_state.js
 * 
 * Gestión de estado de autenticación y sesión de Baileys (WhatsApp MD) usando Redis.
 * 
 * Características principales:
 * - Serialización segura de credenciales y llaves usando BufferJSON (compatibilidad Baileys).
 * - Almacenamiento escalable en Redis:
 *    - Credenciales: 1 key por sesión.
 *    - Llaves: hashes por tipo y sesión (baileys:keys:<sessionId>:<type>).
 *    - Mensajes: 1 key por mensaje con TTL (baileys:messages:<sessionId>:<remoteJid>:<id>).
 *    - Sesiones activas: 1 key por sesión con TTL (baileys:sessions:<sessionId>).
 * - Limpieza dinámica de sesión usando SCAN (elimina todos los datos asociados a una sesión).
 * - Sin caché en memoria: acceso concurrente seguro desde múltiples procesos.
 * - Logging de producción con Pino.
 * 
 * API principal:
 * - RedisAuthState: clase para gestionar el ciclo de vida de una sesión WhatsApp.
 *   - initSession(): inicializa o recupera el estado de sesión.
 *   - saveCreds(): guarda credenciales.
 *   - getMessage()/saveMessage(): recuperación y almacenamiento de mensajes.
 *   - updateSessionStatus(): actualiza el estado de la sesión.
 *   - clearSession(): elimina todos los datos de la sesión en Redis.
 *   - Métodos estáticos para gestión de sesiones activas y limpieza de expiradas.
 * - useRedisAuthState(sessionId): helper para obtener el estado de sesión listo para Baileys.
 * 
 * Uso típico:
 *   const { state, saveCreds, getMessage, saveMessage, clearSession } = await useRedisAuthState();
 *   // Usar state y métodos en la inicialización de Baileys
 * 
 * Notas:
 * - El diseño permite múltiples sesiones (multi-dispositivo) si se parametriza sessionId.
 * - clearSession() es fundamental para forzar la aparición del QR tras logout/login.
 * - No se debe acceder directamente a Redis fuera de este módulo para temas de sesión/llaves.
 */
// whatsapp/auth_state.js
import redisConfig from './config/redis.js';
import { initAuthCreds, BufferJSON } from '@whiskeysockets/baileys';
import pino from 'pino';
const logger = pino({ level: process.env.LOG_LEVEL || 'info' });
const { redis } = redisConfig;
const CREDS_KEY = 'baileys:creds';
const KEYS_KEY = 'baileys:keys';
const MESSAGES_KEY = 'baileys:messages';
const SESSIONS_KEY = 'baileys:sessions';

export class RedisAuthState {
    constructor(sessionId = 'default') {
        this.sessionId = sessionId;
        this.credsKey = `${CREDS_KEY}:${sessionId}`;
        this.keysKey = `${KEYS_KEY}:${sessionId}`;
        this.messagesKey = `${MESSAGES_KEY}:${sessionId}`;
        this.sessionKey = `${SESSIONS_KEY}:${sessionId}`;
    }



    async initSession() {
        try {
            // Cargar credenciales

                let creds = await redis.get(this.credsKey);
                // Cargar credenciales (BufferJSON para compatibilidad Baileys)
            creds = creds ? JSON.parse(creds, BufferJSON.reviver) : initAuthCreds();


            // No se usa caché en memoria para keys, acceso siempre directo a Redis
            const state = {
                creds,
                keys: {
                    get: async (type, ids) => {
                        // Acceso directo a Redis, sin caché en memoria
                        const redisKey = `${this.keysKey}:${type}`;
                        const values = ids.length > 0 ? await redis.hmget(redisKey, ...ids) : [];
                        const result = {};
                        ids.forEach((id, idx) => {
                            const val = values[idx];
                            result[id] = val ? JSON.parse(val, BufferJSON.reviver) : null;
                        });
                        return result;
                    },
                    set: async (data) => {
                        // Acceso directo a Redis, sin caché en memoria
                        for (const type in data) {
                            const redisKey = `${this.keysKey}:${type}`;
                            const entries = [];
                            for (const id in data[type]) {
                                const val = data[type][id];
                                entries.push(id, JSON.stringify(val, BufferJSON.replacer));
                            }
                            if (entries.length > 0) {
                                await redis.hmset(redisKey, ...entries);
                            }
                        }
                    }
                }
            };

            // Registrar sesión activa con TTL
            await redis.setex(this.sessionKey, 7200, JSON.stringify({
                sessionId: this.sessionId,
                lastActive: new Date().toISOString(),
                status: 'connecting'
            }));

            return {
                state,
                saveCreds: async () => {
                    await this.saveCreds(state.creds);
                },
                getMessage: this.getMessage.bind(this),
                saveMessage: this.saveMessage.bind(this),
                updateSessionStatus: this.updateSessionStatus.bind(this),
                clearSession: this.clearSession.bind(this)
            };

        } catch (error) {
            console.error('Error initializing Redis auth state:', error);
            throw error;
        }
    }


    async saveCreds(creds) {
        try {
            await redis.set(this.credsKey, JSON.stringify(creds, BufferJSON.replacer));
            logger.info(`[Redis] Credentials saved for session: ${this.sessionId}`);
        } catch (error) {
            logger.error({ err: error }, `[Redis] Error saving credentials for session: ${this.sessionId}`);
            throw error;
        }
    }
    /**
     * Guarda las credenciales de la sesión en Redis (BufferJSON).
     */

    // Implementación de getMessage requerida por Baileys
    async getMessage(key) {
        try {
            const messageId = `${key.remoteJid}:${key.id}`;
            const redisMsgKey = `baileys:messages:${this.sessionId}:${messageId}`;
            const messageStr = await redis.get(redisMsgKey);
            if (messageStr) {
                const messageData = JSON.parse(messageStr);
                return messageData.message;
            }
            return undefined;
        } catch (error) {
            logger.error({ err: error }, 'Error getting message');
            return undefined;
        }
    }
    /**
     * Recupera un mensaje almacenado en Redis (por key). Requerido por Baileys.
     */

    // Guardar mensaje para getMessage (cada mensaje como key individual con TTL)
    async saveMessage(messageKey, message) {
        try {
            const messageId = `${messageKey.remoteJid}:${messageKey.id}`;
            const redisMsgKey = `baileys:messages:${this.sessionId}:${messageId}`;
            const messageData = {
                key: messageKey,
                message: message,
                timestamp: new Date().toISOString()
            };
            await redis.set(redisMsgKey, JSON.stringify(messageData), 'EX', 30 * 24 * 60 * 60);
        } catch (error) {
            logger.error({ err: error }, 'Error saving message');
        }
    }
    /**
     * Guarda un mensaje en Redis (key individual con TTL). Requerido por Baileys.
     */

    async updateSessionStatus(status, metadata = {}) {
        try {
            const sessionData = {
                sessionId: this.sessionId,
                lastActive: new Date().toISOString(),
                status,
                ...metadata
            };
            await redis.setex(this.sessionKey, 7200, JSON.stringify(sessionData));
            logger.info(`[Redis] Session status updated: ${status} for ${this.sessionId}`);
        } catch (error) {
            logger.error({ err: error }, 'Error updating session status');
        }
    }
    /**
     * Actualiza el estado y metadatos de la sesión activa en Redis (para monitoreo y limpieza).
     */

    async clearSession() {
        try {
            const pipeline = redis.pipeline();
            pipeline.del(this.credsKey);
            // Eliminar todos los hashes de keys de este sessionId (dinámico)
            const keyPattern = `${this.keysKey}:*`;
            let cursor = '0';
            do {
                const [nextCursor, keys] = await redis.scan(cursor, 'MATCH', keyPattern, 'COUNT', 100);
                cursor = nextCursor;
                keys.forEach(key => pipeline.del(key));
            } while (cursor !== '0');

            // Eliminar todos los mensajes individuales de la sesión
            const msgPattern = `baileys:messages:${this.sessionId}:*`;
            cursor = '0';
            do {
                const [nextCursor, keys] = await redis.scan(cursor, 'MATCH', msgPattern, 'COUNT', 100);
                cursor = nextCursor;
                keys.forEach(key => pipeline.del(key));
            } while (cursor !== '0');

            pipeline.del(this.sessionKey);
            await pipeline.exec();
            logger.info(`[Redis] Session cleared: ${this.sessionId}`);
        } catch (error) {
            logger.error({ err: error }, 'Error clearing session');
            throw error;
        }
    }
    /**
     * Elimina todas las credenciales, llaves y mensajes asociados a la sesión en Redis.
     * Fundamental para forzar la aparición del QR tras logout/login.
     */

    // Obtener todas las sesiones activas usando SCAN
    static async scanKeys(pattern) {
        const keys = [];
        let cursor = '0';
        do {
            const [nextCursor, results] = await redis.scan(cursor, 'MATCH', pattern, 'COUNT', 100);
            cursor = nextCursor;
            keys.push(...results);
        } while (cursor !== '0');
        return keys;
    }
    /**
     * Utilidad: obtiene todas las keys que matchean un patrón usando SCAN (no usar KEYS en producción).
     */

    static async getActiveSessions() {
        try {
            const pattern = `${SESSIONS_KEY}:*`;
            const keys = await RedisAuthState.scanKeys(pattern);
            const sessions = [];
            for (const key of keys) {
                const sessionData = await redis.get(key);
                if (sessionData) {
                    sessions.push(JSON.parse(sessionData));
                }
            }
            return sessions;
        } catch (error) {
            logger.error({ err: error }, 'Error getting active sessions');
            return [];
        }
    }
    /**
     * Devuelve la lista de sesiones activas (no expiradas) encontradas en Redis.
     */

    // Limpiar sesiones expiradas
    static async cleanupExpiredSessions() {
        try {
            const sessions = await RedisAuthState.getActiveSessions();
            const expiredSessions = sessions.filter(session => {
                const lastActive = new Date(session.lastActive);
                const now = new Date();
                const diffHours = (now - lastActive) / (1000 * 60 * 60);
                return diffHours > 24; // Considerar expiradas después de 24 horas
            });

            for (const session of expiredSessions) {
                const authState = new RedisAuthState(session.sessionId);
                await authState.clearSession();
                console.log(`[Redis] Cleaned up expired session: ${session.sessionId}`);
            }

            return expiredSessions.length;
        } catch (error) {
            console.error('Error cleaning up expired sessions:', error);
            return 0;
        }
    }
    /**
     * Limpia todas las sesiones expiradas (inactivas >24h) de Redis.
     * Útil para mantenimiento automático.
     */
}

// Función de utilidad para usar en lugar de useRedisAuthState
/**
 * Helper recomendado para obtener el estado de sesión listo para Baileys.
 * Devuelve { state, saveCreds, getMessage, saveMessage, ... }
 */
export async function useRedisAuthState(sessionId = 'default') {
    const authState = new RedisAuthState(sessionId);
    return await authState.initSession();
}