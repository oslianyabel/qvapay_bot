
---

## 13. Aplicar a Oferta P2P

Este endpoint permite a un usuario postularse como contraparte (**Peer**) de una oferta P2P que se encuentre en estado `open`. Al aplicar, la oferta cambia automáticamente a estado `processing`.

### Aplicar a Oferta
`POST /p2p/:uuid/apply`

Este proceso vincula al usuario autenticado con la oferta. Dependiendo del tipo de oferta (`buy` o `sell`), el sistema ejecutará acciones financieras inmediatas sobre el saldo del aplicante.

#### Autenticación
Requiere **Bearer Token** en el header `Authorization`. Es obligatorio que el usuario tenga el **KYC verificado**.

#### Parámetros de Ruta (Path Parameters)
| Parámetro | Tipo | Requerido | Descripción |
| :--- | :--- | :--- | :--- |
| `uuid` | string | **Sí** | Identificador único de la oferta P2P a la que se desea aplicar. |

#### Ejemplo de Request
```bash
curl -X POST "https://api.qvapay.com/p2p/7c9e6679-7425-40de-944b-e07fc1f90ae7/apply" \
  -H "Authorization: Bearer {tu-token}"
```

---

### Flujo de Operación según el Tipo

* **Oferta de Compra (`buy`):** El creador quiere comprar QUSD. El aplicante (tú) actúa como vendedor. Al aplicar, **se te deduce automáticamente** el monto en QUSD de tu saldo y se coloca en garantía (escrow).
* **Oferta de Venta (`sell`):** El creador quiere vender QUSD. El aplicante (tú) actúa como comprador. No se requiere saldo previo en QUSD; simplemente te asignas como la contraparte que enviará el pago externo.

---

### Respuesta Exitosa (201 Created)

```json
{
  "message": "Aplicado a la oferta",
  "p2p": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "transaction": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Campos clave:**
* `p2p`: Confirma el UUID de la oferta procesada.
* `transaction`: UUID de la transacción de débito (solo presente en ofertas `buy`). En ofertas `sell`, este campo será `null`.

---

### Gestión de Errores

| Código | Descripción |
| :--- | :--- |
| **400** | **Error de validación:** KYC no verificado, intento de aplicar a tu propia oferta, saldo insuficiente o límite de operaciones pendientes alcanzado. |
| **401** | **No autorizado:** Token inválido o ausente. |
| **403** | **Prohibido:** Existe un bloqueo entre el creador y el aplicante que impide la operación. |
| **409** | **Conflicto:** La oferta ya no está disponible o ya ha sido tomada por otro usuario. |
| **429** | **Rate limit:** Máximo 2 solicitudes de aplicación cada 60 segundos. |
| **500** | **Error de sistema:** Fallo interno al generar el registro de la transacción. |

---