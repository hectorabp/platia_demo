FROM node:20-alpine

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar package.json y package-lock.json
COPY package.json package-lock.json ./

# Instalar dependencias
RUN npm install

# Copiar el resto de los archivos
COPY config/ ./config
COPY routes/ ./routes
COPY service/ ./service
COPY index.js ./index.js
COPY auth_state.js ./auth_state.js
COPY clean_redis_auth.js ./clean_redis_auth.js


ENV TZ=America/Asuncion

# Exponer el puerto
EXPOSE 3000

# Comando por defecto
CMD ["node", "index.js"]