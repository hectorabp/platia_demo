import axios from 'axios';

export default class HttpClient {
    constructor(baseUrl) {
        this.baseUrl = baseUrl || 'http://backend_encuestador:5000';
    }

    async send({ data = {}, endpoint = '', method = 'POST' }) {
        const url = endpoint ? `${this.baseUrl}/${endpoint}` : this.baseUrl;
        try {
            let response;
            switch (method.toUpperCase()) {
                case 'POST':
                    response = await axios.post(url, data);
                    break;
                case 'GET':
                    response = await axios.get(url, { params: data });
                    break;
                case 'PUT':
                    response = await axios.put(url, data);
                    break;
                case 'DELETE':
                    response = await axios.delete(url, { data });
                    break;
                default:
                    throw new Error(`Método HTTP '${method}' no soportado.`);
            }
            return response.data;
        } catch (error) {
            console.error(`Error al enviar datos a ${url}:`, error.message);
            return null;
        }
    }
}
