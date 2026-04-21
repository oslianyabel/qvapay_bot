## Si la regla seleccionada es "Vender" (vendes QUSD, compras <moneda>)
  - no intentar aplicar ofertas de un monto que exceda el saldo disponible del usuario
  - validar que al ingresar los valores mínimo y máximo de la regla del monto no excedan el saldo actual
  - si se aplican tantas ofertas que el saldo del usuario es <1 debe detenerse el monitoreo y enviar una notificación al usuario
  - validar que al cambiar de Comprar a Vender los valores mínimo y máximo no excedan el saldo actual