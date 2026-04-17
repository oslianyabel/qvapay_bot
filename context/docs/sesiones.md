
---

## 9. Gestión de Sesiones

Este conjunto de endpoints permite al usuario visualizar y administrar todos los dispositivos o navegadores que tienen un acceso activo a su cuenta.

### A. Listar Sesiones Activas
`GET /auth/sessions`

Obtiene una lista detallada de todas las sesiones abiertas, incluyendo información técnica sobre el dispositivo, la dirección IP y la fecha de expiración.

#### Autenticación
Requiere **Bearer Token** en el header `Authorization`.

#### Ejemplo de Request
```bash
curl -X GET https://api.qvapay.com/auth/sessions \
  -H "Authorization: Bearer {tu-token}"
```

#### Respuesta Exitosa (200 OK)
```json
{
  "sessions": [
    {
      "id": "12345",
      "name": "macOS Chrome - 192.168.1.1",
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0...",
      "created_at": "2024-01-15T10:30:00.000Z",
      "expires_at": "2024-07-15T10:30:00.000Z"
    }
  ],
  "currentSessionId": "12345"
}
```

**Campos de respuesta:**
* `sessions`: Array de objetos con los detalles de cada conexión activa.
* `currentSessionId`: Identificador de la sesión desde la cual se está realizando la consulta actual.

---

### B. Eliminar una Sesión Específica
`DELETE /auth/sessions/:id`

Revoca el acceso de un dispositivo específico utilizando su ID de sesión. Si el ID proporcionado corresponde a la sesión actual, el usuario será desconectado inmediatamente y se limpiarán sus credenciales locales (cookies).

#### Parámetros de Ruta (Path Parameters)
| Parámetro | Tipo | Requerido | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | string | **Sí** | El identificador único de la sesión a eliminar. |

#### Ejemplo de Request
```bash
curl -X DELETE https://api.qvapay.com/auth/sessions/12345 \
  -H "Authorization: Bearer {tu-token}"
```

#### Respuesta Exitosa (200 OK)
```json
{
  "message": "Session deleted"
}
```

---

### Gestión de Errores

| Código | Descripción |
| :--- | :--- |
| **400** | **Solicitud incorrecta:** No se proporcionó un ID de sesión válido. |
| **401** | **No autorizado:** Token inválido, expirado o el usuario no tiene permisos sobre la sesión indicada. |

---