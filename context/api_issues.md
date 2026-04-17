# API Issues

## Issue 1

- **API:** QvaPay
- **Endpoint:** `GET /p2p`
- **Descripción:** La documentación describe el payload de respuesta con una clave `offers` para el array de ofertas. En producción, la API devuelve paginación estilo Laravel con la clave `data` en lugar de `offers`, junto con `current_page`, `per_page` y `total`.
- **Solución:** El parser lee primero `data` y si no está presente cae en `offers` como fallback: `response.body.get("data") or response.body.get("offers")`.
