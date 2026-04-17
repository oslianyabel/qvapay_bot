
---

## 10. Mercado P2P (Peer-to-Peer)

Este endpoint permite acceder al listado de ofertas de intercambio entre usuarios. Incluye capacidades de filtrado avanzado, paginación y búsqueda para facilitar la integración de mercados secundarios de divisas.

### Listar Ofertas P2P
`GET /p2p`

Retorna un listado paginado de ofertas disponibles (compra/venta) con información detallada del comerciante y la moneda.

#### Autenticación
Requiere **Bearer Token** en el header `Authorization`.

#### Ejemplo de Request
```bash
curl -X GET "https://api.qvapay.com/p2p?take=20&page=1&type=buy&coin=BANK_CUP" \
  -H "Authorization: Bearer {tu-token}"
```

#### Parámetros de Consulta (Query String)
| Parámetro | Tipo | Descripción |
| :--- | :--- | :--- |
| `page` | number | Número de página (defecto: `1`). |
| `take` | number | Resultados por página (defecto: `20`). |
| `type` | string | Filtrar por tipo: `buy` (compra) o `sell` (venta). |
| `coin` | string | Tick de la moneda (ej: `BANK_CUP`, `CMLC`). |
| `my` | boolean | Si es `true`, muestra solo las ofertas del usuario actual. |
| `min` / `max` | number | Rango de monto para filtrar ofertas. |
| `status` | string | Filtrar por estado (ej: `open`, `completed`). |
| `search` | string | Búsqueda general por descripción o términos. |

---

### Respuesta Exitosa (200 OK)

Retorna un objeto con un array de ofertas. Cada oferta incluye el perfil del usuario (`User`) y los detalles técnicos de la moneda (`Coin`).

```json
{
  "offers": [
    {
      "uuid": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "type": "buy",
      "coin": "BANK_CUP",
      "amount": 50.00,
      "receive": 12500.00,
      "status": "open",
      "only_kyc": 0,
      "only_vip": 0,
      "message": "Pago rápido",
      "created_at": "2024-06-20T14:30:00.000Z",
      "User": {
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "username": "johndoe",
        "kyc": true,
        "vip": false
      },
      "Coin": {
        "tick": "BANK_CUP",
        "name": "Transferencia CUP"
      }
    }
  ]
}
```

**Campos clave de la oferta:**
* `amount`: Cantidad en USD (balance QvaPay).
* `receive`: Cantidad que el usuario recibirá o entregará en la moneda local/destino.
* `only_kyc` / `only_vip`: Restricciones de seguridad de la oferta.

---

### Gestión de Errores

| Código | Descripción |
| :--- | :--- |
| **400** | **Acceso denegado:** El usuario no cumple con los requisitos para usar el P2P (ej. falta verificación). |
| **401** | **No autorizado:** Token inválido o ausente. |
| **429** | **Rate limit:** Límite de 10 solicitudes cada 60 segundos excedido. |

---