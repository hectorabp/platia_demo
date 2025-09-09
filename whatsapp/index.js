// Bandera global para saber si el número está bloqueado
global.isBlocked = false;
// Bandera global para saber si la sesión está realmente conectada
global.isConnected = false;
import { makeWASocket, DisconnectReason } from '@whiskeysockets/baileys';
import qrcode from 'qrcode-terminal';
import QRCode from 'qrcode';
import redisConfig from './config/redis.js';
import { useRedisAuthState } from './auth_state.js';
import express from 'express';
import bodyParser from 'body-parser';
import HttpClient from './service/http_client.js';
import whatsappRoutes from './routes/routes_whatsapp.js';
const { redis, redisPub, redisSub } = redisConfig;
// Declarar la variable para almacenar los últimos mensajes
const ultimosMensajes = [];

// Servidor HTTP Express
const app = express();
app.use(bodyParser.json());

// Montar el router de rutas de WhatsApp en la raíz (se usa Traefik con strip prefix en docker-compose)
app.use('/', whatsappRoutes);

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`Servidor HTTP escuchando en puerto ${PORT}`);
});

const REDIS_CHANNEL = 'whatsapp_platia';


async function connectToWhatsApp () {
    // Autenticación persistente en Redis
    const { state, saveCreds } = await useRedisAuthState();
    if (global.isBlocked) {
        console.warn('[Baileys][connectToWhatsApp] El número está bloqueado. No se intentará reconectar.');
        return;
    }
    const sock = makeWASocket({
        auth: state
    });
    // Hacer el socket global para usarlo en endpoints
    global.sock = sock;

    sock.ev.on('connection.update', (update) => {
        const { connection, lastDisconnect, qr } = update;
        if (qr) {
            qrcode.generate(qr, { small: true });
            // Generar QR como imagen PNG para exponerlo por HTTP
            QRCode.toFile('qr.png', qr, { type: 'png' }, function (err) {
                if (err) console.error('Error generando QR como imagen:', err);
            });
        }

        if (connection === 'close') {
            global.isConnected = false;
            const fecha = new Date();
            const fechaFormateada = fecha.toLocaleString('es-ES', { hour12: false });
            console.log('[Baileys][connection.update] Conexión cerrada, date: ' + fechaFormateada);
            // Usar el patrón recomendado: solo reconectar si NO es logged out
            const isLoggedOut = (lastDisconnect?.error?.output?.statusCode === DisconnectReason.loggedOut);
            console.log('[Baileys][connection.update] isLoggedOut:', isLoggedOut);
            if (!isLoggedOut) {
                console.log('[Baileys][connection.update] Reconectando automáticamente...');
                connectToWhatsApp();
            } else {
                console.log('[Baileys][connection.update] Conexión cerrada. Debes volver a autenticar (escanea el QR).');
            }
        } else if (connection === 'open') {
            global.isConnected = true;
            console.log('[Baileys][connection.update] Conexión abierta');
        }
    });

    sock.ev.on('creds.update', async () => {
        console.log('[Baileys][creds.update] Evento recibido, guardando credenciales en Redis...');
        try {
            await saveCreds();
            console.log('[Baileys][creds.update] Credenciales guardadas correctamente en Redis.');
        } catch (e) {
            console.error('[Baileys][creds.update] Error guardando credenciales en Redis:', e);
        }
    });

    // Escuchar mensajes de WhatsApp y publicar en Redis con el nuevo formato
    sock.ev.on('messages.upsert', async m => {
        if (
            m.messages &&
            m.messages[0] &&
            m.messages[0].key.remoteJid &&
            !m.messages[0].key.fromMe
        ) {
            const msgObj = m.messages[0];
            const mensaje = msgObj.message?.conversation || msgObj.message?.extendedTextMessage?.text || '[Mensaje no textual]';
            let phone = msgObj.key.remoteJid;
            if (phone.includes('@s.whatsapp.net')) {
                phone = phone.replace(/@s\.whatsapp\.net$/, '');
            } else if (phone.includes('-') && phone.includes('@g.us')) {
                phone = phone.split('-')[0];
            }
            // Intentar obtener el nombre del remitente si está disponible
            let name = '';
            if (msgObj.pushName) {
                name = msgObj.pushName;
            } else if (msgObj.participant) {
                name = msgObj.participant;
            }
            // Construir objeto send si hay medios
            let send = {};
            if (msgObj.message?.imageMessage) {
                send.image = '[image]'; // Aquí podrías descargar la imagen si lo deseas
            }
            if (msgObj.message?.audioMessage) {
                send.audio = '[audio]';
            }
            if (msgObj.message?.videoMessage) {
                send.video = '[video]';
            }
            if (msgObj.message?.locationMessage) {
                send.location = {
                    latitude: msgObj.message.locationMessage.degreesLatitude,
                    longitude: msgObj.message.locationMessage.degreesLongitude
                };
            }
            const payload = {
                transmitter: 'whatsapp',
                phone,
                name,
                message: mensaje,
                send
            };
            // Guardar últimos mensajes recibidos para el endpoint HTTP
            ultimosMensajes.unshift({ phone, name, message: mensaje, fecha: new Date().toISOString() });
            if (ultimosMensajes.length > 20) ultimosMensajes.length = 20;
            console.log(`[Mensaje]: Mensaje recibido por ${phone} y enviado a N8N date: ${new Date().toISOString()}`);
            await redisPub.publish(REDIS_CHANNEL, JSON.stringify(payload));
        }
    });

    // Escuchar canal de Redis y enviar mensajes a WhatsApp con el nuevo formato
    redisSub.subscribe(REDIS_CHANNEL, (err, count) => {
        if (err) {
            console.error('Error al suscribirse a Redis:', err);
        } else {
            console.log('Suscrito al canal de Redis:', REDIS_CHANNEL);
        }
    });

    redisSub.on('message', async (channel, message) => {
        if (channel === REDIS_CHANNEL) {
            try {
                // Reemplazar caracteres de control no válidos y limpiar el mensaje
                const sanitizedMessage = message
                    .replace(/\n/g, '\\n') // Escapar saltos de línea
                    .replace(/\u2022/g, '-') // Reemplazar puntos (•) por guiones
                    .replace(/[\x00-\x1F\x7F]/g, ''); // Eliminar caracteres de control no imprimibles
                const data = JSON.parse(sanitizedMessage);
                // Solo procesar si el mensaje viene de N8N y tiene los campos requeridos
                if (data.transmitter === 'N8N' && data.phone && data.message) {
                    const httpClient = new HttpClient();
                    const phones = Array.isArray(data.phone) ? data.phone : [data.phone];
                    let enviados = [];
                    let verificationResults = [];
                    for (const phone of phones) {
                        let surveySent = 'SI';
                        let observation = null;
                        let errorAlEnviar = false;
                        let jid = String(phone).replace(/[^0-9]/g, '') + '@s.whatsapp.net';
                        try {
                            // Siempre intentar enviar el mensaje, confiar en el catch para manejar errores reales
                            if (data.message) {
                                await sock.sendMessage(jid, { text: data.message });
                            }
                            if (data.send && data.send.image) {
                                await sock.sendMessage(jid, { image: { url: data.send.image } });
                            }
                            if (data.send && data.send.audio) {
                                await sock.sendMessage(jid, { audio: { url: data.send.audio }, mimetype: 'audio/mp4' });
                            }
                            if (data.send && data.send.video) {
                                await sock.sendMessage(jid, { video: { url: data.send.video } });
                            }
                            if (data.send && data.send.location && data.send.location.latitude && data.send.location.longitude) {
                                await sock.sendMessage(jid, { location: { degreesLatitude: data.send.location.latitude, degreesLongitude: data.send.location.longitude } });
                            }
                            enviados.push(phone);
                        } catch (err) {
                            console.log(`[Error]: ${err.message}`);
                            surveySent = 'ERROR';
                            observation = err.message;
                            errorAlEnviar = true;
                        }
                        // Si hay verification y no es null, notificar al transmitter
                        if (data.verification && data.verification.id) {
                            function formatDateToMySQL(date) {
                                return date.getFullYear() + '-' +
                                    String(date.getMonth() + 1).padStart(2, '0') + '-' +
                                    String(date.getDate()).padStart(2, '0') + ' ' +
                                    String(date.getHours()).padStart(2, '0') + ':' +
                                    String(date.getMinutes()).padStart(2, '0') + ':' +
                                    String(date.getSeconds()).padStart(2, '0');
                            }
                            const fechaEnvio = formatDateToMySQL(new Date());
                            await httpClient.send({
                                data: {
                                    survey_id: data.verification.id,
                                    phone: phone,
                                    survey_sent: surveySent,
                                    survey_submission_date: fechaEnvio,
                                    observation: observation
                                },
                                endpoint: 'surveys/mark_survey_sent',
                                method: 'POST'
                            });
                            console.log(`[Mensaje]: Estado de envío de encuesta para ${phone}: ${surveySent}, observación: ${observation}, fecha: ${fechaEnvio}`);
                        }
                        verificationResults.push({ phone, surveySent, observation });
                    }
                    if (enviados.length > 0) {
                        console.log(`[Mensaje]: Mensaje recibido por N8N y enviado a ${enviados.join(', ')} date: ${fechaEnvio}`);
                    }
                }
            } catch (e) {
                console.error('[Error]: Error procesando mensaje de Redis:', e);
                console.error('[Error]: Mensaje que causó el error:', message); // Log del mensaje problemático
            }
        }
    });
  }
  // Ejecutar la conexión principal de WhatsApp al iniciar el script
connectToWhatsApp();
