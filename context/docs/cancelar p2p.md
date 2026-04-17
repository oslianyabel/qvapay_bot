
---

## 14. Cancelar Oferta P2P

Este endpoint permite anular una oferta P2P. El resultado de la operación depende directamente del **rol** del usuario (Creador o Contraparte), el **tipo** de oferta (`buy`/`sell`) y su **estado** actual. Los fondos retenidos en garantía (*escrow*) se devuelven automáticamente cuando corresponde.

### Cancelar Oferta
`POST /p2p/:uuid/cancel`

#### Autenticación
Requiere **Bearer Token** en el header `Authorization`.

#### Parámetros de Ruta (Path Parameters)
| Parámetro | Tipo | Requerido | Descripción |
| :--- | :--- | :--- | :--- |
| `uuid` | string | **Sí** | Identificador único de la oferta P2P a cancelar. |

#### Ejemplo de Request
```bash
curl -X POST "https://api.qvapay.com/p2p/7c9e6679-7425-40de-944b-e07fc1f90ae7/cancel" \
  -H "Authorization: Bearer {tu-token}"
```

---

### Matriz de Comportamiento

La lógica de cancelación sigue estas reglas para proteger a ambas partes:

| Tipo | Rol | Estado | Resultado Final |
| :--- | :--- | :--- | :--- |
| **Venta (sell)** | Creador | `open` | Cancelada: Se reembolsa el monto al creador. |
| **Venta (sell)** | Creador | `processing` / `paid` | Pasa a estado **revision** (disputa). |
| **Venta (sell)** | Peer | `processing` / `paid` | La oferta vuelve a `open` (sin peer). |
| **Compra (buy)** | Creador | `open` | Cancelada directamente. |
| **Compra (buy)** | Creador | `processing` / `paid` | Pasa a estado **revision** (disputa). |
| **Compra (buy)** | Peer | `processing` / `paid` | La oferta vuelve a `open` y se reembolsa al peer. |

> **Nota sobre el estado `revision`:** Las ofertas en este estado entran en un proceso de disputa y solo pueden ser resueltas por moderadores o por la parte que realiza el pago externo (fiat).

---

### Respuestas del Servidor

#### A. Cancelación Exitosa (Código 201)
```json
{
  "message": "P2P cancelada",
  "p2p": "7c9e6679-7425-40de-944b-e07fc1f90ae7"
}
```

#### B. Entrada en Revisión (Código 201)
```json
{
  "message": "P2P en revisión",
  "p2p": "7c9e6679-7425-40de-944b-e07fc1f90ae7"
}
```

---

### Gestión de Errores

| Código | Descripción |
| :--- | :--- |
| **400** | **Error de estado:** La oferta ya fue completada, cancelada o no está disponible. |
| **401** | **No autorizado:** Token inválido o ausente. |
| **403** | **Prohibido:** El usuario no tiene permisos sobre esta oferta (no es parte interesada). |
| **404** | **No encontrado:** El UUID de la oferta no existe. |
| **409** | **Conflicto:** El estado de la oferta cambió durante la operación (ej. el peer pagó mientras el creador cancelaba). |
| **429** | **Rate limit:** Límite de 1 solicitud cada 20 segundos. |

---