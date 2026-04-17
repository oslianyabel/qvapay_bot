
---

## Verificación de Sesión

Este endpoint permite validar de forma rápida si un **Token Bearer** sigue siendo válido y no ha expirado. Es especialmente útil para implementar *middlewares* en aplicaciones web o para verificar el estado de la sesión al iniciar un cliente externo (móvil, bot, etc.).

### Verificar Sesión
`POST /auth/check`

Confirma la validez del token enviado en los headers. Si el token ha sido revocado o ha expirado, el servidor denegará el acceso.

#### Autenticación
Requiere incluir el **Bearer Token** en el header `Authorization`.

#### Ejemplo de Request
```bash
curl -X POST https://api.qvapay.com/auth/check \
  -H "Authorization: Bearer {tu-token}"
```

---

### Respuestas del Servidor

#### Sesión Válida (Código 200)
Indica que el token es correcto y el usuario tiene acceso a los recursos protegidos.

```json
{
  "success": "Acceso permitido"
}
```

---

### Gestión de Errores

| Código | Descripción |
| :--- | :--- |
| **401** | **No autorizado:** El token es inválido, ha sido modificado o la sesión ha expirado. |
| **429** | **Rate limit:** Se han realizado demasiadas solicitudes de validación en un corto periodo de tiempo. |

---