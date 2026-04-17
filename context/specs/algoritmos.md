## Algoritmos
- si el usuario pone en las reglas un monto maximo y hay varias ofertas que hacen match con todas las reglas pero no se pueden aplicar todas porque exceden el monto maximo definido en la regla o el saldo disponible en la cuenta del usuario entonces debe aplicarse un algoritmo para que tome la desicion de que conjunto de ofertas seleccionar
  
- almacenar historial de desiciones en un json. 
  - Agrupar ofertas que intervinieron en cada desicion s
  - Por cada oferta de una desicion especifica debe poderse auditar el algoritmo de desicion aplicado, la desicion tomada y el conjunto de ofertas disponibles
  - Por cada oferta disponible debe tenerse en cuenta:
    - moneda
    - ratio
    - monto
    - si se aplico o se descarto
- comando para consultar desiciones tomadas

## criterio de seleccion de ofertas:
- [GREEDY] mayor ratio primero
- [DP] combinacion optima de ofertas que maximicen el monto obtenido