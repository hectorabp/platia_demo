import redis from './config/redis.js';

async function cleanAuthState() {
    await redis.del('baileys:auth_state');
    console.log('Clave de autenticación de Baileys eliminada de Redis.');
    process.exit(0);
}

cleanAuthState();
