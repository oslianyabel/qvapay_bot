
---

## 18. Chat P2P

Este conjunto de endpoints facilita la comunicación directa entre el creador de la oferta y la contraparte (*peer*). Es el canal oficial para coordinar detalles del pago fiat, enviar comprobantes y resolver dudas durante el proceso de intercambio.

### A. Obtener Mensajes del Chat
`GET /p2p/:uuid/chat`

Recupera el historial completo de mensajes asociados a una oferta específica.

#### Autenticación
Requiere **Bearer Token** en el header `Authorization`.

#### Ejemplo de Request
```bash
curl -X GET "https://api.qvapay.com/p2p/7c9e6679-7425-40de-944b-e07fc1f90ae7/chat" \
  -H "Authorization: Bearer {tu-token}"
```

#### Respuesta Exitosa (200 OK)
```json
{
  "message": "chat",
  "chat": [
    {
      "id": "1",
      "p2p_id": "123",
      "peer_id": "550e8400-e29b-41d4-a716-446655440000",
      "message": "Hola, ya realicé la transferencia",
      "image": null,
      "created_at": "2024-06-20T14:35:00.000Z",
      "is_moderator": false
    }
  ]
}
```

---

### B. Enviar Mensaje o Imagen
`POST /p2p/:uuid/chat`

Permite enviar texto o archivos de imagen (comprobantes). Solo los participantes de la oferta pueden interactuar en este chat.

#### Escenario 1: Mensaje de Texto (JSON)
* **Header:** `Content-Type: application/json`
* **Body:** `{"message": "Texto del mensaje"}` (Máx. 599 caracteres).

#### Escenario 2: Enviar Imagen (FormData)
* **Header:** `Content-Type: multipart/form-data`
* **Campos:** * `file`: Archivo (JPG, PNG, GIF).
    * `message`: (Opcional) Texto que acompaña la imagen.

> **Nota técnica:** Las imágenes se redimensionan automáticamente a un máximo de **1000x1000 px** para optimizar el almacenamiento y la carga.

#### Ejemplo de Request (Imagen)
```bash
curl -X POST "https://api.qvapay.com/p2p/7c9e6679-7425-40de-944b-e07fc1f90ae7/chat" \
  -H "Authorization: Bearer {tu-token}" \
  -F "file=@comprobante.jpg" \
  -F "message=Aquí está el comprobante"
```

#### Respuesta Exitosa (200 OK)
```json
{
  "message": "12345"
}
```
*El campo `message` retorna el ID único del nuevo mensaje creado.*

---

### Gestión de Errores

| Código | Descripción |
| :--- | :--- |
| **400** | **Error de validación:** Mensaje vacío, excede los 599 caracteres o el formato de imagen no es válido. |
| **401** | **No autorizado:** Token inválido o ausente. |
| **403** | **Prohibido:** El usuario no es participante (Creador o Peer) de la oferta. |
| **404** | **No encontrado:** El UUID de la oferta P2P no existe. |
| **500** | **Error de servidor:** Fallo crítico al procesar la subida del archivo. |

---