
---

## 19. Promedios P2P (Tasas de Cambio)

Este endpoint público permite obtener las tasas de cambio promedio del mercado P2P basadas en las operaciones completadas exitosamente en las últimas **24 horas**. Es ideal para aplicaciones que necesiten mostrar el precio del mercado en tiempo real o sugerir montos competitivos al crear ofertas.

### Obtener Promedios de Tasas
`GET /p2p/averages`

Retorna los promedios calculados mediante el ratio `receive / amount`, agrupados por cada moneda disponible en la plataforma.

#### Autenticación
**No requiere.** Este es un endpoint público.

#### Ejemplo de Request
```bash
curl -X GET "https://api.qvapay.com/p2p/averages"
```

---

### Respuesta Exitosa (200 OK)

La respuesta es un objeto donde cada llave es el "tick" de la moneda (ej. `BANK_CUP`).

```json
{
  "BANK_CUP": {
    "name": "Transferencia CUP",
    "average": 250.5,
    "average_buy": 248.0,
    "average_sell": 253.0,
    "count": 45,
    "count_buy": 20,
    "count_sell": 25,
    "updated_at": "2024-06-20T14:30:00.000Z"
  },
  "BANK_MLC": {
    "name": "Transferencia MLC",
    "average": 1.05,
    "average_buy": 1.03,
    "average_sell": 1.07,
    "count": 30,
    "updated_at": "2024-06-20T14:30:00.000Z"
  }
}
```

#### Detalle de Campos por Moneda
| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `average` | number | Tasa promedio general de la moneda. |
| `average_buy` | number | Tasa promedio específica para ofertas de **compra**. |
| `average_sell`| number | Tasa promedio específica para ofertas de **venta**. |
| `count` | number | Volumen total de ofertas completadas en las últimas 24h. |
| `updated_at` | string | Fecha y hora del último recálculo de datos. |

---

### Rendimiento y Cache
Para garantizar la escalabilidad y rapidez de la respuesta, este endpoint utiliza una estrategia de almacenamiento en caché:

* **Redis:** Los datos se almacenan en una base de datos en memoria y se recalculan periódicamente desde la base de datos principal.
* **Headers de Cache:** La respuesta incluye `Cache-Control: public, max-age=60`, lo que indica que el cliente o los nodos intermedios pueden considerar el dato fresco durante 60 segundos.
* **Revalidación:** Se admite `stale-while-revalidate=120` para servir datos ligeramente antiguos mientras se refresca el cache en segundo plano.

---