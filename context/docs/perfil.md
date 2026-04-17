
---

## 23. Perfil de Usuario

Este endpoint es el recurso central para obtener la información completa del usuario autenticado. Además de los datos demográficos y de seguridad, incluye el balance actual y las **3 transacciones más recientes**, permitiendo una carga de interfaz más eficiente al evitar peticiones adicionales.

### Obtener Mi Perfil
`GET /user`

#### Autenticación
Requiere **Bearer Token** en el header `Authorization`.

#### Ejemplo de Request
```bash
curl -X GET https://api.qvapay.com/user \
  -H "Authorization: Bearer {tu-token}"
```

---

### Respuesta Exitosa (200 OK)

Retorna un objeto detallado con el estado de la cuenta, balances y actividad.

```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "username": "juan123",
  "balance": 150.75,
  "kyc": true,
  "p2p_enabled": true,
  "latest_transactions": [
    {
      "uuid": "txn-uuid",
      "amount": 10.00,
      "description": "Pago de servicio",
      "status": "paid",
      "App": { "name": "Mi App" }
    }
  ]
}
```

#### Campos Principales de Respuesta

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `uuid` | string | Identificador único global del usuario. |
| `balance` | number | Saldo disponible en USD (QUSD). |
| `kyc` | boolean | Indica si el usuario ha completado la verificación de identidad. |
| `golden_check` | boolean | `true` si el usuario tiene una suscripción Gold activa (sin comisiones P2P). |
| `p2p_enabled` | boolean | Estado del acceso al mercado de intercambio entre pares. |
| `two_factor_secret`| string | Retorna `***` si el 2FA está activo, de lo contrario `null`. |
| `latest_transactions`| array | Listado de los últimos 3 movimientos financieros (incluye objetos `App`, `User` y `PaidBy`). |

---

### Detalles de Seguridad y Redes Sociales
El objeto también expone rutas para recursos visuales (`image`, `cover`) y nombres de usuario para integraciones sociales (`twitter`, `telegram`), facilitando la personalización del perfil en la interfaz de usuario.

---

### Gestión de Errores

| Código | Descripción |
| :--- | :--- |
| **401** | **No autorizado:** El token proporcionado es inválido, ha sido revocado o no se incluyó en la petición. |

---