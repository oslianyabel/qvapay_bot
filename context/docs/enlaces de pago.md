
---

## 20. Enlaces de Pago (Payment Links)

Este conjunto de endpoints permite a los usuarios crear, listar y eliminar enlaces de pago personalizados. Son ideales para integrar cobros rápidos en sitios web o compartir directamente con clientes.

### A. Listar Enlaces de Pago
`GET /user/payment-links`

Obtiene la colección de enlaces de pago del usuario, ordenados cronológicamente de forma descendente.

#### Autenticación
Requiere **Bearer Token** en el header `Authorization`.

#### Ejemplo de Request
```bash
curl -X GET "https://api.qvapay.com/user/payment-links?product_id=prod_001" \
  -H "Authorization: Bearer {tu-token}"
```

**Parámetros de Query:**
* `product_id` (Opcional): Filtra los resultados para un producto específico.

#### Respuesta Exitosa (200 OK)
```json
[
  {
    "id": "1",
    "name": "Suscripción mensual",
    "product_id": "prod_001",
    "amount": 9.99,
    "created_at": "2026-03-17T12:00:00.000Z"
  }
]
```

---

### B. Crear Enlace de Pago
`POST /user/payment-links`

Genera un nuevo enlace de pago asociado a un producto y un monto específico.

#### Request Body (JSON)
| Parámetro | Tipo | Requerido | Descripción |
| :--- | :--- | :--- | :--- |
| `name` | string | **Sí** | Nombre descriptivo del enlace. |
| `product_id` | string | **Sí** | Identificador interno de tu producto. |
| `amount` | number | **Sí** | Monto a cobrar (debe ser positivo). |

#### Ejemplo de Request
```bash
curl -X POST https://api.qvapay.com/user/payment-links \
  -H "Authorization: Bearer {tu-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Suscripción mensual",
    "product_id": "prod_001",
    "amount": 9.99
  }'
```

---

### C. Eliminar Enlace de Pago
`DELETE /user/payment-links`

Elimina de forma permanente un enlace de pago del registro del usuario.

#### Request Body (JSON)
* `id` (String, **Requerido**): El identificador único del enlace a eliminar.

#### Ejemplo de Request
```bash
curl -X DELETE https://api.qvapay.com/user/payment-links \
  -H "Authorization: Bearer {tu-token}" \
  -H "Content-Type: application/json" \
  -d '{ "id": "1" }'
```

#### Respuesta Exitosa (200 OK)
```json
{
  "message": "Payment link deleted"
}
```

---

### Gestión de Errores

| Código | Descripción |
| :--- | :--- |
| **400** | **Solicitud incorrecta:** Datos faltantes, monto inválido o ID no proporcionado en el borrado. |
| **401** | **No autorizado:** Token de acceso inválido, expirado o ausente. |
| **404** | **No encontrado:** El enlace de pago no existe o no pertenece a tu cuenta. |

---