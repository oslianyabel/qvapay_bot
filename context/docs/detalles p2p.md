
---

## 11. Detalle de Oferta P2P

Este endpoint permite obtener la información exhaustiva de una oferta individual utilizando su identificador único (UUID). Es fundamental para visualizar los pasos de una transacción en curso o revisar una operación finalizada.

### Obtener Detalle de Oferta
`GET /p2p/:uuid`

Retorna los datos completos de la oferta, incluyendo información sensible que solo se revela a las partes involucradas (creador y contraparte).

#### Autenticación
Requiere **Bearer Token** en el header `Authorization`.

#### Parámetros de Ruta (Path Parameters)
| Parámetro | Tipo | Requerido | Descripción |
| :--- | :--- | :--- | :--- |
| `uuid` | string | **Sí** | Identificador único de la oferta P2P. |

#### Ejemplo de Request
```bash
curl -X GET "https://api.qvapay.com/p2p/7c9e6679-7425-40de-944b-e07fc1f90ae7" \
  -H "Authorization: Bearer {tu-token}"
```

---

### Respuesta Exitosa (200 OK)

```json
{
  "message": "P2P",
  "p2p": {
    "uuid": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "type": "buy",
    "coin": "BANK_CUP",
    "amount": 50.00,
    "receive": 12500.00,
    "status": "open",
    "details": { "cuenta": "1234567890" },
    "User": {
      "username": "johndoe",
      "kyc": true
    },
    "Peer": null,
    "Coin": {
      "tick": "BANK_CUP",
      "name": "Transferencia CUP"
    },
    "Ratings": [],
    "currentUserId": "12345"
  }
}
```

#### Notas sobre la Visibilidad de Datos
* **Campos Privados:** Los campos `details` (ej. números de cuenta) y `tx_id` solo son visibles si el usuario autenticado es el **creador** (`User`) o el **interesado** (`Peer`) de la oferta.
* **Calificaciones:** Si la oferta tiene el estado `completed`, el array `Ratings` contendrá las valoraciones emitidas por ambas partes.

---

### Gestión de Errores

| Código | Descripción |
| :--- | :--- |
| **400** | **Solicitud inválida:** UUID no proporcionado o acceso P2P no habilitado para la cuenta. |
| **401** | **No autorizado:** Token de autenticación inválido o ausente. |
| **403** | **Prohibido:** Un bloqueo mutuo entre usuarios impide visualizar la información. |
| **404** | **No encontrado:** La oferta no existe, el usuario no tiene permisos para verla (privada) o no cumple los requisitos de KYC/VIP. |

---