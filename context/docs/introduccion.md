
---

# Documentación de la API de QvaPay

Guía de integración con la API de QvaPay para aceptar pagos, gestionar balances, aplicar a ofertas P2P y realizar cobros automáticos.

## 1. Introducción
La API de QvaPay permite integrar pagos digitales directamente en cualquier aplicación (tiendas online, bots de Telegram, apps móviles, etc.).

**Capacidades principales:**
* Crear y gestionar facturas de pago con URLs compartibles.
* Ejecutar cobros directos a usuarios con pagos recurrentes autorizados.
* Consultar transacciones y estados en tiempo real.
* Obtener información de la cuenta y balance.

## 2. Configuración General

### URL Base
Todas las peticiones deben dirigirse a:
`https://api.qvapay.com`

### Autenticación
La API soporta dos métodos de autenticación:

#### A. Bearer Token (Usuario)
Para aplicaciones que actúan en nombre de un usuario.
* **Header:** `Authorization: Bearer {token}`
* **Obtención:** Se recibe en el endpoint de login.
* **Expiración:** 2 horas (por defecto) o 180 días (con opción "recordarme").

```bash
curl -X GET https://api.qvapay.com/user/balance \
  -H "Authorization: Bearer {token}"
```

#### B. Credenciales de App (App-ID + App-Secret)
Para integraciones servidor-a-servidor (backend).
* **Headers:** * `app-id: {tu-app-uuid}`
    * `app-secret: {tu-app-secret}`
* **Obtención:** En el panel de QvaPay > Mis Aplicaciones.

```bash
curl -X POST https://api.qvapay.com/v2/balance \
  -H "Content-Type: application/json" \
  -H "app-id: {tu-app-uuid}" \
  -H "app-secret: {tu-app-secret}"
```

### Comparativa de Métodos
| Método | Caso de Uso | Endpoints comunes |
| :--- | :--- | :--- |
| **Bearer Token** | Apps móviles, bots de usuario | `/user/*`, `/transaction/*`, `/p2p/*` |
| **Credenciales App** | Pasarelas, cobros auto, backend | `/v2/*` (facturas, cobros) |

*Nota: Si un endpoint acepta ambos, las credenciales de app tienen prioridad.*

---

## 3. Límites y Formatos

### Rate Limiting
* **Endpoints de cobro:** 5 requests / 20 segundos por app.
* **Endpoints generales:** 3 requests / 5 segundos.
* *Error 429:* Aplicar backoff exponencial si se excede el límite.

### Formato de Respuesta
Todas las respuestas son **JSON**.

**Respuesta Exitosa (200 OK):**
```json
{
  "message": "Operación exitosa",
  "data": { ... }
}
```

**Respuesta de Error:**
```json
{
  "error": "Descripción del error"
}
```

### Códigos de Estado HTTP
| Código | Significado |
| :--- | :--- |
| **200** | Operación exitosa |
| **400** | Datos faltantes o validación fallida |
| **401** | Credenciales inválidas o expiradas |
| **403** | Sin permisos para la operación |
| **404** | Recurso no encontrado |
| **429** | Rate limit excedido |
| **500** | Error interno del servidor |

---

## 4. Detalles Adicionales

### Comisiones
* Detalles por moneda en [coins.qvapay.com](https://coins.qvapay.com).
* **Cargo automático:** 0.5% (deducida del pagador). 
* **Plan GOLD:** Comisión de procesamiento exonerada (waived).

### Webhooks
Al crear una factura, puedes definir una URL de webhook. QvaPay enviará un **POST** a esa URL cuando el estado de la factura cambie a pagada para automatizar la confirmación en tu sistema.

### Soporte
Únete a la comunidad de desarrolladores en Telegram: [Grupo de Desarrolladores QvaPay](https://t.me/qvapay_devs)

---

## 5. Próximos Pasos Recomendados
1.  **Info:** Verifica la validez de tus credenciales.
2.  **Balance:** Consulta los fondos disponibles.
3.  **Crear Factura:** Genera tu primer enlace de pago.
4.  
