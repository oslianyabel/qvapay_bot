
---

## Autenticación de Usuario (Login)

Este endpoint permite iniciar sesión con credenciales de usuario para obtener un **Token Bearer**. Este token es necesario para interactuar con los recursos que actúan en nombre de una cuenta personal.

### Login
`POST /auth/login`

Autentica a un usuario mediante correo electrónico y contraseña. El proceso implementa **Autenticación de Dos Factores (2FA)** obligatoria, ya sea mediante un PIN enviado por correo o un código OTP (Authenticator App).

> **Nota de Seguridad:** Si el usuario tiene activo el código OTP, el PIN de 4 dígitos quedará inhabilitado para este endpoint por motivos de seguridad.

#### Flujo de Autenticación
1.  **Paso 1:** Envía el `email` y `password` (sin el campo `two_factor_code`).
2.  **Paso 2:** Si las credenciales son válidas, el servidor responderá con un código **202 Accepted**.
3.  **Paso 3:** Reenvía la petición incluyendo el `two_factor_code` (PIN de 4 dígitos o OTP de 6 dígitos).

#### Request Body
```json
{
  "email": "usuario@ejemplo.com",
  "password": "contraseña123",
  "remember": true,
  "two_factor_code": "1234"
}
```

#### Parámetros del Body
| Parámetro | Tipo | Requerido | Descripción |
| :--- | :--- | :--- | :--- |
| `email` | string | **Sí** | Correo electrónico de la cuenta. |
| `password` | string | **Sí** | Contraseña del usuario. |
| `remember` | boolean | No | `true`: Token expira en 180 días. `false`: Expira en 2 horas. |
| `two_factor_code`| string | No | PIN de 4 dígitos (email) o OTP de 6 dígitos. |

---

### Respuestas del Servidor

#### A. Requerimiento de 2FA (Código 202)
Indica que las credenciales son correctas pero se necesita el segundo factor para completar el acceso.
```json
{
  "info": "Código 2FA requerido",
  "notified": false,
  "has_otp": true
}
```

#### B. Login Exitoso (Código 200)
Retorna el token de acceso y la información del perfil del usuario.
```json
{
  "accessToken": "203955|abc123...",
  "token_type": "Bearer",
  "me": {
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "email": "usuario@ejemplo.com",
    "name": "Juan",
    "username": "juan123",
    "balance": "150.75"
  }
}
```

**Campos clave de respuesta:**
* `accessToken`: El token que debe incluirse en el header `Authorization`.
* `me`: Objeto con detalles del usuario como `uuid`, `username` y `balance` actual.
* `security_warning`: Objeto presente si la contraseña ha sido detectada en filtraciones externas de datos.

---

### Gestión de Errores

| Código | Descripción |
| :--- | :--- |
| **400** | Request inválido (faltan campos obligatorios). |
| **401** | Credenciales incorrectas o cuenta inexistente/inactiva. |
| **403** | Contraseña comprometida. Se sugiere la acción `reset_password`. |
| **423** | Cuenta bloqueada temporalmente por exceso de intentos fallidos. |
| **429** | Rate limit excedido para intentos de login. |