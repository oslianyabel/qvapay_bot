
---

## 12. Crear Oferta P2P

Este endpoint permite publicar una nueva intención de compra o venta en el mercado P2P. Es un proceso síncrono que requiere que el usuario tenga su identidad verificada (**KYC**).

### Crear Oferta
`POST /p2p/create`

Permite establecer las condiciones de intercambio, restricciones de seguridad y canales de notificación.

> **Importante:** En las ofertas de tipo **sell** (venta), el monto especificado en `amount` se deduce y bloquea automáticamente del saldo del usuario al momento de la creación.

#### Autenticación
Requiere **Bearer Token** en el header `Authorization`.

#### Ejemplo de Request
```bash
curl -X POST "https://api.qvapay.com/p2p/create" \
  -H "Authorization: Bearer {tu-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "buy",
    "coin": "BANK_CUP",
    "amount": 50,
    "receive": 12500,
    "details": [{ "name": "cuenta", "value": "1234567890" }],
    "only_kyc": 0,
    "message": "Pago rápido"
  }'
```

#### Parámetros del Body (JSON)
| Parámetro | Tipo | Requerido | Descripción |
| :--- | :--- | :--- | :--- |
| `type` | string | **Sí** | `buy` (compra) o `sell` (venta). |
| `coin` | string/num | **Sí** | Tick de la moneda (ej: `BANK_CUP`) o ID numérico. |
| `amount` | number | **Sí** | Cantidad en QUSD (Rango: 0.1 - 100,000). |
| `receive` | number | **Sí** | Cantidad en la moneda destino (Rango: 0.1 - 1,000,000). |
| `details` | array | **Sí** | Datos de pago (ej: `[{"name": "cuenta", "value": "..."}]`). |
| `only_kyc` | number | No | `1` para restringir a usuarios verificados. |
| `private` | number | No | `1` para ocultar la oferta del canal público de Telegram. |
| `webhook` | string | No | URL para recibir notificaciones de cambio de estado. |

---

### Respuesta Exitosa (201 Created)

```json
{
  "msg": "Oferta P2P creada correctamente",
  "p2p": {
    "uuid": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "status": "open",
    "details": { "cuenta": "1234567890" },
    "created_at": "2024-06-20T14:30:00.000Z"
  }
}
```

#### Webhook de Creación
Si se definió una URL de `webhook`, QvaPay enviará un **POST** con la siguiente estructura inmediatamente tras la creación:

```json
{
  "operation": "created",
  "p2p": { ... }
}
```

---

### Gestión de Errores

| Código | Descripción |
| :--- | :--- |
| **400** | **Error de validación:** Datos inválidos, moneda inexistente, falta de KYC, saldo insuficiente o límite de ofertas activas alcanzado. |
| **401** | **No autorizado:** Token inválido o ausente. |
| **429** | **Rate limit:** Máximo 1 solicitud cada 5 segundos (límite de 100 diarias). |
| **500** | **Error de sistema:** Fallo interno al procesar la transacción en base de datos. |

---