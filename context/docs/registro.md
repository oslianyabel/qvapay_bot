
---

## Registro de Usuario

Este endpoint permite la creación de una nueva cuenta en la plataforma QvaPay. Al completar el registro, el sistema envía automáticamente un correo electrónico de verificación con un PIN al usuario.

### Registro
`POST /auth/register`

Crea un nuevo perfil de usuario. Es obligatorio aceptar los términos y condiciones, y el sistema realiza validaciones estrictas sobre la calidad del correo electrónico (no se permiten correos temporales o desechables).

#### Request Body
```json
{
  "name": "Juan",
  "lastname": "Pérez",
  "email": "usuario@ejemplo.com",
  "password": "contraseña123",
  "invite": "username_invitador",
  "terms": true
}
```

#### Parámetros del Body
| Parámetro | Tipo | Requerido | Descripción |
| :--- | :--- | :--- | :--- |
| `name` | string | **Sí** | Nombre del usuario (2 a 50 caracteres). |
| `lastname` | string | **Sí** | Apellido del usuario (2 a 50 caracteres). |
| `email` | string | **Sí** | Email válido con registros MX (no desechable). |
| `password` | string | **Sí** | Contraseña segura (8 a 20 caracteres). |
| `invite` | string | No | Username del usuario que realizó la invitación. |
| `terms` | boolean | **Sí** | Debe ser `true` para procesar el registro. |

---

### Respuestas del Servidor

#### Registro Exitoso (Código 201)
Retorna un mensaje de confirmación y los datos básicos del perfil creado, incluyendo su identificador único (UUID).

```json
{
  "message": "Registro exitoso",
  "user": {
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "email": "usuario@ejemplo.com",
    "name": "Juan",
    "username": "juan123"
  }
}
```

---

### Gestión de Errores

| Código | Descripción |
| :--- | :--- |
| **400** | Datos inválidos: términos no aceptados, contraseña débil o el email ya está registrado. |
| **403** | Registro bloqueado: Se ha detectado comportamiento de bot o se ha excedido el límite de registros permitidos. |

---