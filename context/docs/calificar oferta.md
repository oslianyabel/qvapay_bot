
---

## 17. Calificar Oferta P2P

Este endpoint permite a los usuarios evaluar la experiencia de intercambio tras completar una oferta. Las calificaciones son fundamentales para construir la reputación y el nivel de confianza de los comerciantes dentro del ecosistema P2P de QvaPay.

### Calificar a la Contraparte
`POST /p2p/:uuid/rate`

Solo los participantes directos de la operación (**Creador** o **Peer**) pueden emitir una calificación, y solo se permite una evaluación por cada parte involucrada por cada oferta completada.

#### Autenticación
Requiere **Bearer Token** en el header `Authorization`.

#### Ejemplo de Request
```bash
curl -X POST "https://api.qvapay.com/p2p/7c9e6679-7425-40de-944b-e07fc1f90ae7/rate" \
  -H "Authorization: Bearer {tu-token}" \
  -H "Content-Type: application/json" \
  -d '{
    "rating": 5,
    "comment": "Excelente operación, muy rápido",
    "tags": ["rapido", "confiable"]
  }'
```

#### Parámetros del Body (JSON)
| Parámetro | Tipo | Requerido | Descripción |
| :--- | :--- | :--- | :--- |
| `rating` | number | **Sí** | Escala numérica del **1 al 5**. |
| `comment` | string | No | Breve descripción de la experiencia (máx. 120 caracteres). |
| `tags` | array | No | Etiquetas predefinidas: `rapido`, `confiable`, `comunicacion`. |

---

### Respuesta Exitosa (200 OK)

```json
{
  "message": "Rating created",
  "ratingId": "12345",
  "rating": 5
}
```

**Campos de respuesta:**
* `ratingId`: Identificador único de la calificación generada.
* `rating`: El valor numérico asignado.

---

### Gestión de Errores

| Código | Descripción |
| :--- | :--- |
| **400** | **Solicitud inválida:** Datos mal formateados, falta el valor de `rating` o el usuario ya emitió una calificación para esta oferta anteriormente. |
| **401** | **No autorizado:** Token inválido o ausente. |
| **403** | **Prohibido:** El usuario autenticado no fue participante (Creador o Peer) de la oferta especificada. |
| **404** | **No encontrado:** El UUID de la oferta P2P no existe en el sistema. |

---