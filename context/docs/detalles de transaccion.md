
---

## 22. Detalle de Transacción

Este endpoint permite obtener la información técnica y administrativa completa de una operación única. A diferencia del listado general, este recurso desglosa todas las relaciones de la transacción, incluyendo detalles de billeteras (wallets), servicios P2P, retiros y carritos de compra asociados.

### Obtener Detalle de Transacción
`GET /transaction/:uuid`

Retorna el objeto extendido de una transacción. Es el endpoint ideal para verificar el éxito de un pago desde un backend o para mostrar un comprobante detallado al usuario final.

#### Autenticación
Soporta ambos métodos de seguridad:
* **Bearer Token:** En el header `Authorization`.
* **Credenciales de App:** Headers `app-id` y `app-secret`.

#### Parámetros de Ruta (Path Parameters)
| Parámetro | Tipo | Requerido | Descripción |
| :--- | :--- | :--- | :--- |
| `uuid` | string | **Sí** | Identificador único (UUID) de la transacción a consultar. |

#### Ejemplo de Request
```bash
curl -X GET "https://api.qvapay.com/transaction/7c9e6679-7425-40de-944b-e07fc1f90ae7" \
  -H "Authorization: Bearer {tu-token}"
```

---

### Respuesta Exitosa (200 OK)

La respuesta agrupa la información en un objeto `data` que contiene todas las entidades relacionadas.

```json
{
  "message": "Transaction 7c9e6679",
  "data": {
    "uuid": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "amount": "25.00",
    "status": "paid",
    "description": "Pago de servicio",
    "remote_id": "order-12345",
    "user": {
      "username": "janedoe",
      "kyc": true
    },
    "paid_by": {
      "username": "johndoe",
      "kyc": true
    },
    "app": {
      "name": "Mi App",
      "url": "https://example.com"
    },
    "wallet": null,
    "p2p": null,
    "withdraw": null,
    "service": null
  }
}
```

#### Desglose de Objetos Relacionados
* **`user` / `paid_by`**: Identifican al receptor y al emisor del pago respectivamente.
* **`app`**: Detalles de la aplicación si el pago fue procesado vía API de comercio.
* **`wallet`**: Si la transacción implica criptomonedas, incluye dirección de destino, red (moneda) y el `txid` de la blockchain.
* **`p2p`**: Si la transacción nace de una oferta P2P, incluye el tipo de oferta y su estado.
* **`withdraw`**: Detalles técnicos en caso de que la transacción sea un retiro de fondos.
* **`service`**: Información sobre el producto o servicio digital adquirido (si aplica).

---

### Gestión de Errores

| Código | Descripción |
| :--- | :--- |
| **401** | **No autorizado:** Las credenciales proporcionadas son inválidas o han expirado. |
| **404** | **No encontrado:** El UUID no existe o la transacción no pertenece al usuario/app autenticada. |

---