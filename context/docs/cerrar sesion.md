
---

## Cierre de Sesión (Logout)

QvaPay ofrece dos mecanismos para invalidar tokens de acceso: uno para la sesión activa y otro para forzar la salida de todos los dispositivos conectados a la cuenta.

### A. Cerrar Sesión Actual
`GET /auth/logout`

Invalida el token de acceso utilizado en la petición actual. Ideal para implementar el botón de "Salir" en aplicaciones cliente.

#### Autenticación
Requiere **Bearer Token** en el header `Authorization` o la cookie `qpsess`.

#### Ejemplo de Request
```bash
curl -X GET https://api.qvapay.com/auth/logout \
  -H "Authorization: Bearer {tu-token}"
```

**Respuesta Exitosa (200 OK):**
```json
{
  "message": "Logged out"
}
```

---

### B. Cerrar Todas las Sesiones
`DELETE /auth/logout`

Revoca **todos** los tokens de acceso activos asociados al usuario en todos los dispositivos y navegadores. Este es un mecanismo de seguridad recomendado si el usuario sospecha que su cuenta ha sido comprometida.

#### Autenticación
Requiere **Bearer Token** en el header `Authorization` o la cookie `qpsess`.

#### Ejemplo de Request
```bash
curl -X DELETE https://api.qvapay.com/auth/logout \
  -H "Authorization: Bearer {tu-token}"
```

**Respuesta Exitosa (200 OK):**
```json
{
  "message": "Logged out from all devices"
}
```

---

### Gestión de Errores (Ambos métodos)

| Código | Descripción |
| :--- | :--- |
| **400** | **Sesión inválida:** El token proporcionado no existe o ya ha sido invalidado anteriormente. |
| **401** | **No autorizado:** No se proporcionó ningún token de autenticación en la cabecera. |

---