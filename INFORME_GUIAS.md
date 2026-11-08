# Revisión de guías de RutaXP 0.7.12

## Recorrido del pícaro humano

[Ver el informe por paso, incluidas las recompensas y las discrepancias por verificar](PICARO_HUMANO.md).

## El Páramo de los Ancianos (0.7.11)

La segunda visita a Onus sitúa la aceptación de «Fuerzas henchidas» después de su requisito 950. En el viaje a Vallefresno la guía enlaza la aceptación de «El despertar» con la escolta hasta la bolsa en Costa Oscura y la entrega a Liladris en Atalaya de Maestra. El objetivo consulta el diario del personaje. Las marcas manuales antiguas de desplazamiento y de lectura quedan en la copia de progreso de la revisión anterior.

## Costa Oscura y capítulos siguientes: revisión 0.7.10

El catálogo pasa a 57 guías, 2.343 pasos y 7.455 objetivos. Se conservan los 7.444 objetivos originales y se añaden 11 acciones para tres misiones previas que faltaban. La única corrección de un mapa original es el muelle de Auberdine: mantiene 32.4, 43.8, pero ahora pertenece a Costa Oscura (1439), no a Claro de la Luna (1450). Las demás posiciones originales se mantienen.

Se reprodujo la captura de la caja mecánica 827 con dos patas de seis y una omisión manual. La entrega seleccionada quedaba oculta mientras aparecía bloqueada la caja 411. El panel mantiene visible el objetivo seleccionado, identifica la previa pendiente y permite iniciar su recuperación con un clic. No interpreta una omisión como entrega. Los datos desconocidos tampoco autorizan avanzar; las pruebas de dos jugadores esperan el crédito real del compañero.

La cadena 827 → 411 → 323 → 525 conserva el orden y los destinos de entrega comprobados. Holy Diver ahora exige las nueve misiones de criaturas varadas, se acepta en el paso 33, se completa en el 34 y se entrega en el 37. La discrepancia con la fuente que solo declaraba una previa permanece explícita. Jai’vhanel requiere nivel 15. Las visitas de druida mantienen sus condiciones y la misión de Pesca sigue permitiendo aprender la profesión.

El barrido posterior recorre 24 capítulos de Alianza. Se incorporan Nek’rosh (474), la primera flor de Nord’el (98208) y la primera tarea contra los Faucedraco (98291), con aceptación, trabajo y entrega antes de sus continuaciones. Los objetivos añadidos y cada traslado tienen evidencia y mapas de migración; las marcas antiguas nunca se asignan a una acción nueva.

Quedan dos incidencias explícitas en `RutaXP/Source/successor_review.json`: las fuentes discrepan en el requisito de La Forjaluz (526); para Una fiesta en tu honor (1271), dos fuentes añaden 1258 y la guía original no lo hace. Incorporar esta última cadena requiere resolver un desplazamiento adicional entre continentes. No se presenta esa parte como reparada ni se impone un requisito sin recorrido. El resto de advertencias de fuentes permanece en el informe de requisitos. Esta auditoría no equivale a completar todas las rutas dentro de Forever.

## Requisitos y profesiones: revisión 0.7.9

El catálogo actual tiene 57 guías, 2.338 pasos, 7.444 objetivos y 1.900 IDs distintos de misión. Se compararon las 2.290 aceptaciones con datos de disponibilidad fijados de EverythingQuests, complementados con comprobaciones de AllTheThings para Forever. 1.846 IDs tienen algún dato incorporado al informe; 54 todavía no. De estos últimos, 45 aparecen en otros bloques de AllTheThings pendientes de revisar e incorporar. Tener algún dato no garantiza que todos los requisitos de esa misión estén documentados.

Se revisó el orden de cadenas en seis guías: Ingeniería de Páramos, Zephras de Alianza, Crestagrana, Mulgore, Claros de Tirisfal y Bosque de Argénteos. Se añadieron siete visitas para entregar los requisitos antes de aceptar y realizar las misiones siguientes, conservando todos los objetivos y sus destinos. Otras 28 aceptaciones en 16 guías recibieron requisitos corroborados que faltaban, sin cambiar su orden. Las revisiones guardan las pruebas y los mapas exactos para conservar el progreso entre versiones.

El motor comprueba las profesiones por ID y rango. Una profesión ausente aparta las tareas que todavía no están aceptadas; una respuesta desconocida no se interpreta como ausencia. Las misiones ya activas o entregadas conservan su estado real. Las profesiones son ramas personales en dúo; no se supone que el compañero tenga la misma profesión. Ingeniería 1/2 y 2/2 de Páramos requieren Ingeniería, y la segunda se acepta después de entregar la primera. Su objetivo comprueba la misión completa y explica todos los materiales.

Los posibles requisitos contradictorios, encargos opcionales que llevan al mismo NPC, alternativas y condiciones activas sin corroboración suficiente permanecen en el informe. No se han aplicado como bloqueos automáticos. Las pruebas son de datos y simulaciones de funcionamiento; falta recorrer las rutas corregidas dentro de Forever.

Para reproducir la auditoría usa `python tools/audit_quest_requirements.py --check`. La evidencia con versiones, líneas, huellas y limitaciones está en `RutaXP/Source/quest_requirements_evidence.json`; el informe, en `quest_requirements_audit.json`; las revisiones aplicadas, en `guide_revisions.json`. Las licencias y créditos figuran en `NOTICE.md` y `RutaXP/Licenses/`.

## Revisión anterior 0.6.6

Se revisaron las 57 guías, sus 2.330 pasos y los 7.444 objetivos. La auditoría comprueba datos, fuentes, instrucciones y navegación del addon; no certifica haber recorrido cada misión dentro de WoW Forever.

## Estructura, cadenas y planificación

La revisión de estructura sigue las trayectorias `next` por separado y aplica las condiciones de clase y raza. Comprueba aceptación, trabajo, entrega y requisitos sin mezclar el historial de rutas alternativas. Las misiones de recados, compras, objetos que inician misión y trabajo descrito en notas se revisan por separado: la ausencia del verbo `complete` no demuestra por sí sola un fallo.

Se corrigió un fallo del motor: una rama descartada al aceptar podía reaparecer más tarde como entrega obligatoria. Las reproducciones incluyen 5261/33 en Elwynn, 415/413 en Dun Morogh y 5241/5211 en Un'Goro. El motor respeta la rama elegida y conserva cualquier misión que realmente siga activa en el diario.

«En busca de calor» (99159) conserva su secuencia: aceptar en el paso 37 de Dun Morogh, reunir 14 leños en el 38 y entregar al Padre Gavin en el 39. Si ya está aceptada antes, el panel muestra esos pasos y sus contadores. La vista previa ya no pide repetir objetivos que el juego da por terminados. El plan informa sin avanzar el cursor, aceptar misiones ni cambiar la flecha.

Las discrepancias de las fuentes y los límites de la auditoría se conservan en `RutaXP/Source/guide_structure.json`. La base de datos discrepa con el recorrido de las misiones 4492/4491; la escolta 5321 se describe en notas y se difiere a otra guía. No se altera el orden de esas cadenas sin comprobar su comportamiento real en el cliente. El modelo de auditoría tampoco verifica qué combinaciones de raza y clase permite el servidor.

| Resultado | Objetivos |
|---|---:|
| Con destino estático documentado | 7.142 |
| Con destino para una parte del objetivo y otra acción de inventario | 2 |
| Sin pin fijo por la naturaleza de la acción | 300 |
| Sin clasificación o ubicación pendiente | 0 |
| Coordenadas inválidas en la comprobación | 0 |

Los 433 objetivos que antes carecían de una solución de navegación se reparten entre 422 destinos nuevos y 11 acciones especiales. Los nuevos destinos incluyen 41 rutas de vuelo por aprender, 45 posadas y 165 acciones de volar. Para volar se señalan orígenes compatibles conectados al destino, sin dar por aprendida una ruta que el juego no confirme.

Las 300 acciones sin pin fijo incluyen 64 misiones que empiezan con un objeto, 84 piedras de hogar, 25 requisitos de nivel y 116 notas, además de 11 casos documentados de inventario, habilidad o escolta. Dos escoltas conservan sus puntos de inicio como referencias de fuente; la flecha no hace volver allí mientras toca seguir al NPC. Una escolta con salida explícita conserva esa referencia y exige la confirmación real de la misión.

Cada objetivo tiene una instrucción de presentación en español. Las instrucciones se construyen a partir de acción, nombres, cantidades, procedencia y notas de la guía; 18 casos especiales tienen una revisión específica documentada. El panel conserva contadores y pistas cortas; las mecánicas y notas completas quedan en el tooltip. Usa «Domestica» en ocho objetivos cuyo crédito interno era de tipo `kill`.

Se conservaron todas las acciones, IDs de misión, índices de objetivo, objetos, cantidades, condiciones, requisitos, orden de guías y los 6.560 puntos directos originales. Las coordenadas añadidas proceden del mismo commit de SendaFH/Polestar que las guías, de sus bases de datos y de acciones explícitas publicadas. Cada candidato nuevo tiene su evidencia, archivo y huella SHA-256. No se añadieron alturas no documentadas.

## Límites que siguen visibles

Las fuentes originales tienen seis objetivos sin explicación propia suficiente. Sus instrucciones de presentación ahora incluyen información específica contrastada; la auditoría conserva la carencia original para no confundir una mejora local con una fuente ya corregida.

Las misiones 91899 y 91904 de cajas tienen notas contradictorias sobre cómo se consiguen. Se indica verificar los materiales de la caja y el requisito del registro antes de entregarla. Se conserva el texto original en los datos, pero se aparta ese contexto contradictorio de la presentación. No se afirma que un NPC regale la caja ni que haya que abrir una caja ya sellada.

La malla de terreno y las coordenadas siguen dependiendo de la versión y fase de Forever. Una posición documentada no garantiza una ruta transitable en una fase nueva, una entrada o un piso sin altura conocida. Siguen vigentes las comprobaciones de navegación y la confirmación manual de accesos y transportes que la requieren.

## Reproducibilidad

- `RutaXP/Source/guide_audit.json`: inventario por guía, acción y excepción.
- `RutaXP/Source/guide_structure.json`: continuidad, condiciones, ramas y límites por trayectoria.
- `python tools/audit_guide_structure.py --check`: comprueba la auditoría de estructura; requiere el repositorio fuente fijado en `.sources/SendaFH` y Lua mediante lupa.
- `RutaXP/Source/guide_locations.json`: correcciones de navegación con evidencia y archivos fuente.
- `RutaXP/Source/guide_instructions_evidence.json`: mecánicas específicas contrastadas.
- `python tools/refresh_guides.py --check`: verifica instrucciones, correcciones y auditoría sin escribir.
- `python tools/refresh_guides.py`: regenera el snapshot revisado, los datos Lua y la auditoría.
- `python tools/guide_coordinates.py`: reconstruye las propuestas desde el repositorio fuente fijado; requiere ese repositorio y Lua mediante lupa.

El constructor normal `python RutaXP/Source/build_guides.py` sigue funcionando sin conexión ni repositorio externo. No se modifican el progreso ni los archivos de personaje durante ninguna de estas comprobaciones.
