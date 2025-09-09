# WhatsApp Redis Bridge

Este proyecto implementa un puente entre WhatsApp y Redis utilizando la librería [Baileys](https://github.com/WhiskeySockets/Baileys) para interactuar con WhatsApp Web y [ioredis](https://github.com/luin/ioredis) para la comunicación con Redis. Permite enviar y recibir mensajes de WhatsApp a través de un canal de Redis, facilitando la integración con otros sistemas como N8N.

## ¿Cómo funciona?

- **Recepción de mensajes de WhatsApp:**
  - El bot escucha mensajes entrantes en WhatsApp.
  - Cuando recibe un mensaje, lo publica en un canal de Redis (`whatsapp`) con un formato JSON estructurado.

- **Envío de mensajes a WhatsApp:**
  - El bot se suscribe al canal de Redis (`whatsapp`).
  - Cuando recibe un mensaje en el canal, lo envía a uno o varios destinatarios en WhatsApp, soportando texto, imágenes, audio, video y ubicación.

## Estructura del mensaje

El formato de los mensajes intercambiados por Redis es:

```json
{
  "transmitter": "whatsapp|N8N",
  "phone": "595983285109" | ["595983285109", "595981234567"],
  "name": "John Doe",
  "message": "Hello, World!",
  "send": {
    "image": "path/to/image.png",
    "audio": "path/to/audio.mp3",
    "video": "path/to/video.mp4",
    "location": { "latitude": 37.7749, "longitude": -122.4194 }
  }
}
```

- `transmitter`: Indica el origen del mensaje (`whatsapp` o `N8N`).
- `phone`: Número(s) de teléfono en formato internacional (puede ser string o array).
- `name`: Nombre del remitente (si está disponible).
- `message`: Texto del mensaje.
- `send`: Objeto opcional con rutas/URLs de medios a enviar.

## Instalación

1. Clona el repositorio y entra en la carpeta del proyecto.
2. Instala las dependencias:
   
   ```bash
   yarn install
   # o
   npm install
   ```

3. Configura las variables de entorno si es necesario (host, puerto y contraseña de Redis).

4. Ejecuta el proyecto:
   
   ```bash
   node index.js
   ```

   O usando Docker:
   
   ```bash
   docker build -t whatsapp-redis .
   docker run --env REDIS_HOST=host --env REDIS_PASSWORD=pass whatsapp-redis
   ```

## Uso

- **Primer inicio:**
  - Al iniciar el bot por primera vez, se mostrará un código QR en la terminal. Escanéalo con WhatsApp para autenticarte.
  - Las credenciales se guardan en la carpeta `auth_info_baileys` para futuros inicios automáticos.

- **Recibir mensajes:**
  - Cada mensaje recibido en WhatsApp se publica en el canal Redis `whatsapp` con el formato descrito.

- **Enviar mensajes:**
  - Publica un mensaje en el canal Redis `whatsapp` con `transmitter: "N8N"` y los campos requeridos. El bot lo enviará a WhatsApp.
  - Soporta envío de texto, imágenes, audio, video y ubicación.

## Ejemplo de publicación en Redis para enviar mensaje

```json
{
  "transmitter": "N8N",
  "phone": ["595983285109", "595981234567"],
  "message": "¡Hola desde N8N!",
  "send": {
    "image": "https://ejemplo.com/imagen.png"
  }
}
```

## Personalización y ampliación

- Puedes modificar la lógica para agregar más tipos de mensajes o integrar con otros sistemas.
- El archivo `documentacion.txt` contiene ejemplos avanzados de uso de Baileys, como manejo de grupos, multimedia, presencia, privacidad, etc.

## Dependencias principales

- [baileys](https://www.npmjs.com/package/baileys): Cliente WhatsApp Web multi-dispositivo.
- [ioredis](https://www.npmjs.com/package/ioredis): Cliente Redis para Node.js.
- [qrcode-terminal](https://www.npmjs.com/package/qrcode-terminal): Muestra el QR en la terminal para autenticación.

## Notas de seguridad

- Las credenciales de WhatsApp se almacenan en la carpeta `auth_info_baileys`. No compartas ni subas estos archivos a repositorios públicos.
- Asegúrate de proteger el acceso a tu instancia de Redis.

## Recursos adicionales

- Consulta `documentacion.txt` para ejemplos avanzados y detalles de la API de Baileys.
- [Repositorio oficial de Baileys](https://github.com/WhiskeySockets/Baileys)

---

**Autor:**
- Basado en Baileys y Redis, adaptado para integración con N8N y otros sistemas.
