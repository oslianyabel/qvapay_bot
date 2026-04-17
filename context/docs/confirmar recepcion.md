
---

## 16. Confirmar Recepción P2P

Este endpoint representa el paso final del intercambio. Al ejecutarlo, el usuario confirma que ha recibido el pago en moneda local (fiat) de forma satisfactoria. El sistema libera entonces los fondos en QUSD de la custodia (*escrow*) hacia el destinatario final.

### Confirmar Recepción
`POST /p2p/:uuid/received`

#### Autenticación
Requiere **Bearer Token** en el header `Authorization`.

#### Parámetros de Ruta (Path Parameters)
| Parámetro | Tipo | Requerido | Descripción |
| :--- | :--- | :--- | :--- |
| `uuid` | string | **Sí** | Identificador único de la oferta P2P a completar. |

#### Ejemplo de Request
```bash
curl -X POST "https://api.qvapay.com/p2p/7c9e6679-7425-40de-944b-e07fc1f90ae7/received" \
  -H "Authorization: Bearer {tu-token}"
```

---

### Responsabilidad y Comisiones

#### ¿Quién debe confirmar?
Solo la parte que **recibe el dinero fiat** tiene el permiso para liberar los QUSD:

| Tipo de Oferta | Quién recibe el Fiat | Quién ejecuta `/received` |
| :--- | :--- | :--- |
| **Venta (sell)** | El Creador (`User`) | El Creador (`User`) |
| **Compra (buy)** | La Contraparte (`Peer`) | La Contraparte (`Peer`) |

#### Comisiones de Red
Se aplica una comisión por servicio del **0.25%** sobre el monto bruto de la operación.
> **Excepción:** Los usuarios que posean la verificación **Golden Check** están exentos de esta comisión (0%).

---

### Respuesta Exitosa (201 Created)

```json
{
  "message": "P2P Recibido",
  "p2p": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "amount": 49.88,
  "fee": 0.12,
  "gross_amount": 50.00
}
```

**Campos de respuesta:**
* `amount`: Monto neto que recibe el destinatario (tras deducir comisión).
* `fee`: Valor de la comisión aplicada a la transacción.
* `gross_amount`: Monto total original de la operación.

---

### Notificación vía Webhook
Si la oferta fue creada con una URL de webhook, QvaPay enviará un **POST** automático con el estado final:

```json
{
  "operation": "completed",
  "p2p": {
    "uuid": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "status": "completed",
    "updated_at": "2024-06-20T15:00:00.000Z"
  }
}
```

---

### Gestión de Errores

| Código | Descripción |
| :--- | :--- |
| **401** | **No autorizado:** Token inválido o ausente. |
| **403** | **Prohibido:** El usuario no es quien recibe el fiat o la oferta no está en un estado que permita la liberación (ej. no ha sido marcada como `paid`). |
| **404** | **No encontrado:** El UUID de la oferta no existe. |
| **409** | **Conflicto:** La oferta ya ha sido completada o los participantes han cambiado durante el proceso. |
| **429** | **Rate limit:** Límite de 1 solicitud cada 5 segundos. |