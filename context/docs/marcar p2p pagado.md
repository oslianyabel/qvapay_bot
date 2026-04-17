
---

## 15. Marcar P2P como Pagado

Este endpoint permite notificar a la plataforma y a la contraparte que el pago en moneda local (fiat) ha sido realizado. Al ejecutar esta acción, la oferta cambia de estado `processing` a `paid`.

### Marcar como Pagado
`POST /p2p/:uuid/paid`

Este paso es fundamental para que el sistema de custodia (*escrow*) sepa que el proceso de intercambio externo ha concluido y que los fondos en QUSD pueden ser liberados próximamente.

#### Autenticación
Requiere **Bearer Token** en el header `Authorization`.

#### Ejemplo de Request
```bash
curl -X POST "https://api.qvapay.com/p2p/7c9e6679-7425-40de-944b-e07fc1f90ae7/paid" \
  -H "Authorization: Bearer {tu-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "tx_id": "REF-123456789"
  }'
```

#### Parámetros
* **Ruta (Path):** `uuid` (String, requerido) - UUID de la oferta.
* **Cuerpo (JSON):** `tx_id` (String, requerido) - Referencia o número de comprobante de la transferencia realizada.

---

### Responsabilidad de Marcado

Solo la parte que **envía el dinero fiat** tiene el permiso técnico para ejecutar este endpoint:

| Tipo de Oferta | Quién envía el Fiat | Quién ejecuta `/paid` |
| :--- | :--- | :--- |
| **Compra (buy)** | El Creador (`User`) | El Creador (`User`) |
| **Venta (sell)** | La Contraparte (`Peer`) | La Contraparte (`Peer`) |

---

### Respuesta Exitosa (200 OK)

```json
{
  "message": "P2P marcado como pagado"
}
```

---

### Gestión de Errores

| Código | Descripción |
| :--- | :--- |
| **400** | **Error de validación:** `tx_id` ausente o la oferta no está en estado `processing`. |
| **401** | **No autorizado:** Token inválido o ausente. |
| **403** | **Prohibido:** El usuario autenticado no es quien debe realizar el pago según el tipo de oferta. |
| **404** | **No encontrado:** El UUID de la oferta no existe. |
| **409** | **Conflicto:** El estado de la oferta cambió o el peer fue desasignado durante la operación. |
| **429** | **Rate limit:** Límite de 1 solicitud cada 10 segundos. |

---