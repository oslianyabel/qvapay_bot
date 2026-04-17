
---

## 21. Listado de Transacciones

Este endpoint permite recuperar el historial detallado de movimientos financieros del usuario. Cuenta con un sistema robusto de filtros para auditoría, conciliación y exportación de datos.

### Consultar Transacciones
`GET /transaction`

Retorna un listado paginado de las transacciones (enviadas o recibidas) asociadas al usuario autenticado.

#### Autenticación
Requiere **Bearer Token** en el header `Authorization`.

#### Ejemplo de Request
```bash
curl -X GET "https://api.qvapay.com/transaction?take=10&page=1&status=paid&include_total=true" \
  -H "Authorization: Bearer {tu-token}"
```

#### Parámetros de Consulta (Query String)
| Parámetro | Tipo | Descripción |
| :--- | :--- | :--- |
| `take` | number | Resultados por página (1-30, defecto: `20`). |
| `page` | number | Número de página (defecto: `1`). |
| `status` | string | Filtrar por: `paid`, `pending`, `cancelled`. |
| `search` | string | Búsqueda por descripción, UUID o ID remoto. |
| `date_from` | string | Fecha inicio en formato ISO 8601 (ej: `2024-01-01`). |
| `include_total`| string | Si es `true`, la respuesta cambia a un objeto con el conteo total. |
| `download` | string | Si es `true`, el servidor retorna un archivo **.xlsx (Excel)**. |

---

### Respuestas del Servidor

#### A. Respuesta Estándar (Array)
Por defecto, el endpoint retorna un array de objetos de transacción.

```json
[
  {
    "uuid": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "amount": 25.00,
    "description": "Pago de servicio",
    "remote_id": "order-12345",
    "status": "paid",
    "created_at": "2024-06-20T14:30:00.000Z",
    "App": { "name": "Mi App" },
    "PaidBy": { "username": "johndoe" },
    "User": { "username": "janedoe" }
  }
]
```

#### B. Con Conteo Total (`include_total=true`)
```json
{
  "transactions": [ ... ],
  "total": 150
}
```

**Campos clave del objeto:**
* `uuid`: Identificador único global de la transacción.
* `remote_id`: Referencia externa proporcionada por el comercio o aplicación.
* `PaidBy` / `User`: Identifican quién emitió el pago y quién lo recibió respectivamente.
* `App`: Si la transacción se generó a través de una aplicación integrada, incluye su información.

---

### Gestión de Errores

| Código | Descripción |
| :--- | :--- |
| **400** | **Solicitud incorrecta:** El parámetro `take` está fuera del rango permitido (1-30). |
| **401** | **No autorizado:** Token de acceso inválido, expirado o ausente. |
| **429** | **Rate limit:** Límite de 3 solicitudes cada 5 segundos excedido. |

---