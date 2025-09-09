import Redis from 'ioredis';

const REDIS_PASSWORD = process.env.REDIS_PASSWORD || '22242sadasd2522';
const REDIS_HOST = process.env.REDIS_HOST || 'localhost';
const REDIS_PORT = process.env.REDIS_PORT || 6379;

const redis = new Redis({ host: REDIS_HOST, port: REDIS_PORT, password: REDIS_PASSWORD }); // general
const redisPub = new Redis({ host: REDIS_HOST, port: REDIS_PORT, password: REDIS_PASSWORD }); // para publish
const redisSub = new Redis({ host: REDIS_HOST, port: REDIS_PORT, password: REDIS_PASSWORD }); // para subscribe

export default { redis, redisPub, redisSub };
