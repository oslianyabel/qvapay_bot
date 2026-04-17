## Si la regla seleccionada es "Comprar"
  - no intentar aplicar ofertas de un monto que exceda el saldo disponible por el usuario
  - validar que al ingresar los valores minimo y maximo de la regla del monto no excedan el saldo actual
  - si se aplican tantas ofertas que el saldo del usuario es <1 debe detenerse el monitoreo y enviar una notificacion al usuario
  - validar que al cambiar de vender para comprar los valores minimo y maximo no excedan el saldo actual