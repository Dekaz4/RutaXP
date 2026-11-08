# RutaXP 0.7.12 para WoW Forever

Guías de leveo en español, flecha de navegación, talentos e instructor de clase. Abre la biblioteca con `/rutaxp` o `/rutas`.

## Instalar y actualizar con el mismo setup

Descarga [Instalador_RutaXP.exe](https://github.com/Dekaz4/RutaXP/releases/latest/download/Instalador_RutaXP.exe). El mismo archivo sirve para los dos jugadores y para instalar, actualizar o reparar. Guárdalo fuera de `Interface/AddOns/RutaXP`.

1. Cierra WoW y ejecuta el setup.
2. Elige **Instalar o actualizar**. La primera vez selecciona tu carpeta de Forever; queda recordada en ese ordenador.
3. El programa descarga la última versión publicada en GitHub, verifica los archivos y conserva una copia anterior. Después abre WoW desde tu acceso habitual.

No requiere cuenta de GitHub ni modifica el progreso de `WTF`. Si ya tienes la versión actual y sus archivos están correctos, lo indica. Las siguientes veces podéis ejecutar el mismo setup: no hace falta descargarlo otra vez para cada actualización del addon.

**Si falla:** usa **Reparar** para volver a descargar la versión actual o **Restaurar** para recuperar una copia anterior válida. Si GitHub no está disponible, **Instalar copia incluida** utiliza los archivos del propio EXE; esa copia puede ser anterior a la publicada. El setup no baja de versión mediante instalación o actualización normal. Si falla al activar una instalación, intenta restaurar automáticamente la anterior.

El setup no abre WoW, no instala comprobadores en segundo plano y no bloquea el addon por versión. Ejecutadlo ambos cuando publiquemos cambios. `/rutaxp actualizar` muestra el enlace al setup y vuestra versión; el addon no consulta GitHub desde el juego.

### Publicar una versión nueva

Modifica la versión del TOC y el valor de respaldo de `Updates.lua`, confirma y sube los cambios de código a GitHub. Después ejecuta `python tools/publish_release.py --publish --notes-file notas.txt`, con las notas de la versión en ese archivo. La herramienta construye, prueba, sube a un borrador y verifica los archivos antes de publicar la versión completa. Un cambio de código no cuenta como actualización hasta publicar su release.

## Pícaro humano (0.7.12)

La ruta reúne las visitas a los mismos personajes en Villanorte, Auberdine, Villa del Lago y otros centros de misiones. En solitario, durante una visita del paso actual, la flecha puede señalar una entrega lista si estás hablando con ese personaje o lo tienes seleccionado al alcance. En grupo se sigue el recorrido común.

Desde nivel 10, Keryn y Mathias Shaw te guían hasta la Hoja de Astucia. Al aceptar o entregar una misión, pasa el ratón sobre la pista de equipo para ver las armas, el cuero, las capas y los accesorios que puedes conseguir. Verás cuáles recibes automáticamente, entre cuáles puedes elegir y la diferencia con tu equipo cuando WoW proporciona los datos. La Hermandad de los Defias incluye una indicación opcional para conseguir la túnica de VanCleef en grupo. [Recorrido del pícaro humano paso a paso](PICARO_HUMANO.md).

## Arbal y la escolta de Kerlonian (0.7.11)

En Costa Oscura, entrega «Vuelve con Onus» antes de hablar con Arbal para «Fuerzas henchidas». La guía reserva «El despertar» para el viaje a Vallefresno. Acepta la misión de Kerlonian, acompáñalo hasta su bolsa y sigue hasta Liladris Rioluna para entregarla dentro del tiempo. Al acercarte para aceptar o entregar una misión, la flecha muestra con quién hablar.

## Costa Oscura y continuidad de Alianza (0.7.10)

Si una misión previa está omitida, el panel muestra su nombre y conserva los contadores reales. Una entrega pendiente ya no queda oculta mientras la flecha apunta a ella. Pulsa con el botón izquierdo una misión bloqueada para retomar sus requisitos con un recorrido de recuperación; al terminarlos vuelve al punto guardado. El clic derecho sigue permitiendo recuperar una fila omitida. La flecha muestra el requisito pendiente en lugar de llevarte a una entrega que todavía no puedes hacer.

Comprobadas las cuatro cajas mecánicas de Costa Oscura, sus entregas y la espera entre dos jugadores. Holy Diver se acepta después de entregar las nueve misiones de criaturas varadas, se completa durante el regreso al norte y se entrega al volver a Auberdine. El destino del muelle usa ahora el mapa de Costa Oscura. Jai’vhanel requiere nivel 15 y las visitas de druida mantienen sus condiciones.

Revisados los 24 capítulos de Alianza desde Costa Oscura hasta el final de la ruta. Se añaden tres misiones previas omitidas —Nek’rosh, la primera flor de Nord’el y la primera tarea contra los Faucedraco— con aceptación, objetivos y entrega antes de sus continuaciones en Hillsbrad. Se conservan los objetivos originales y se trasladan sus marcas de progreso a las posiciones nuevas.

La revisión es de fuentes y simulaciones, no una certificación de cada misión dentro del juego. Siguen pendientes las discrepancias de **La Forjaluz (526)** y **Una fiesta en tu honor (1271)**; esta última necesitaría además resolver el recorrido de su posible requisito 1258. Se documentan en `RutaXP/Source/successor_review.json` y no se añaden bloqueos sin una solución comprobada.

## Requisitos y cadenas de misiones (0.7.9)

Se corrigen el orden y los requisitos de cadenas en Páramos de Poniente, Zephras de Alianza, Crestagrana, Mulgore, Claros de Tirisfal y Bosque de Argénteos. Además, 28 aceptaciones en 16 guías comprueban ahora una misión previa que ya se entregaba en el recorrido. Las correcciones están contrastadas con EverythingQuests y AllTheThings para Forever; las alternativas o requisitos contradictorios quedan documentados sin aplicarlos automáticamente.

Las misiones de profesión comprueban la profesión y el rango del personaje. Si no la tiene, se aparta esa tarea; si ya lleva la misión en el diario, se sigue mostrando. En dúo son tareas personales y después se vuelve a esperar en los pasos compartidos. La rama opcional de Ingeniería de Páramos pide primero completar su primera misión y después reunir todos los materiales de la segunda.

Los cambios de orden conservan las marcas de cada objetivo, los puntos personales y los marcadores de recuperación. Una cadena afectada puede retomar una tarea anterior pendiente; las guías ya terminadas conservan su final. La interfaz de Antigravity se mantiene.

La auditoría cubre las **57 guías y 1.900 IDs de misión**. Hay 54 IDs cuyos datos de disponibilidad todavía no están incorporados al informe y otras discrepancias pendientes de comprobar en el juego. El informe reproducible está en `RutaXP/Source/quest_requirements_audit.json`: revisar todas las guías no significa haber validado todas las misiones jugando.

## Orden de las misiones de Alba (0.7.8)

En Páramos de Poniente, «El estado de las minas» requiere entregar primero **Probar los pozos y Branquias de múrloc**. La ruta recoge las branquias antes de visitar las minas y vuelve a Alba Lunajusta para entregar ambas misiones y aceptar la siguiente. Sus requisitos se comprueban también al recuperar una cadena.

Las partidas anteriores conservan sus objetivos, omisiones y confirmaciones al cambiar los números de paso. Si esta cadena os había dejado bloqueados, la guía retoma la tarea que falta según el diario de cada personaje. También se corrige la recuperación antigua de esta misión. El modo dúo sigue esperando el progreso real del compañero.

Requisito contrastado con [EverythingQuests](https://github.com/wheelbarrel00/EverythingQuests/blob/54a16756db16adeb9d5602bace1507077df37185/Data/QuestAvailable_Forever.lua#L15279). La revisión de software no sustituye la comprobación dentro de Forever.

## Volver a un paso saltado (0.7.7)

Al volver con **Atrás** a un paso con tareas omitidas, esas tareas recuperan su estado pendiente y la flecha vuelve a guiarlas. Los objetivos que el juego confirma como completados muestran su resultado real. La recuperación funciona también al acompañar al amigo y permite continuar con el avance automático al terminar.

## Misiones omitidas y progreso real (0.7.6)

Las tareas saltadas se muestran en gris con «Omitido». Puedes recuperarlas con clic derecho sobre su fila. Las misiones entregadas muestran «Misión entregada» y los objetivos terminados muestran su resultado, evitando los contadores antiguos a cero.

Escribe `/rutaxp pendientes` para retomar el primer objetivo pendiente de tu diario en la guía seleccionada. Se recuperan las omisiones de esas tareas y se actualiza el estado que recibe tu compañero. También está en Herramientas → Bloqueos → Retomar misiones pendientes.

## Viajes entre todas las guías (0.7.5)

Las 57 guías de leveo incluyen 55 enlaces. Al terminar una zona, el recorrido indica dónde embarcar, qué salida tomar y dónde reunirse para empezar el siguiente capítulo. Las dos últimas guías, una por facción, cierran el recorrido. En un transporte sigue la indicación del panel hasta desembarcar. Si te falta un destino de vuelo, usa **Ir sin vuelo** cuando aparezca en el puesto del maestro.

Con el dúo automático, cada uno ve la flecha desde su posición. El que se adelanta espera en las paradas compartidas y en el punto de llegada. Si el juego bloquea la comunicación, reuníos físicamente en el destino y pulsad **Empezar aquí** en ambos ordenadores. Cada personaje mantiene sus misiones y sus pasos guardados.

## Viaje de Dun Morogh a Páramos de Poniente (0.7.4)

Al terminar Dun Morogh, el panel y la flecha indican el próximo tramo del viaje hasta Colina del Centinela. Si ya vas por Ventormenta, Villadorada o Páramos, la guía retoma el camino desde tu zona. En el Tren Subterráneo, el panel explica cuándo subir y salir. Al llegar al poblado, aparecen las misiones de Páramos.

Cada miembro del dúo recibe indicaciones desde su propia posición. Con la espera activada, la guía espera en la colina hasta que llegue el compañero. Si el juego restringe los mensajes de grupo, al llegar podéis pulsar **Empezar aquí** en cada ordenador. Los personajes que ya habían terminado Dun Morogh o estaban empezando Páramos pueden retomar el viaje con su progreso guardado.

## Misiones de clase y cambio de zona en dúo (0.7.3)

En Dun Morogh, el cazador enano hace las tres domas de Grif en Kharanos y entrega «Entrenar a la bestia» a Belia en Forjaz. El paladín usa el Símbolo de la Vida sobre Narm Faulk antes de hablar con él. En el modo automático, cada uno puede ver su propia visita de clase aunque el compañero vaya más atrás. El Tren Subterráneo reúne las dos ramas en el paso 73.

Cuando ambos terminan Dun Morogh, el dúo acuerda continuar en Páramos de Poniente. Con el avance manual, el botón **Continuar** confirma el cambio. Cada personaje conserva el progreso que ya tenía en la siguiente guía. Si falta comunicación entre ambos addons, el panel indica la espera.

El panel Dúo se abre con un resumen. **Ver detalles y herramientas** da acceso a las opciones avanzadas.

## Detección del compañero y talentos a nivel 9 (0.7.2)

Con los dos personajes en grupo, RutaXP reconoce las formas completas del nombre y apellido del compañero que proporciona Forever. Cuando el juego rechaza un envío, el addon consulta el motivo y vuelve a intentarlo respetando el ritmo del canal de grupo. Con `/rutaxp conexion` cada jugador puede ver su versión y saber si WoW acepta sus envíos y si le llega la guía del compañero.

Antes del nivel 10, el panel de talentos muestra el primer punto previsto para la guía elegida. Al desbloquear talentos compara la guía con el árbol que devuelve el cliente.

## Avance y sincronización del dúo (0.7.1)

Se corrige una espera que podía mantener el paso completado en verde: otras consultas desplazaban los datos de una misión necesaria del compañero. El intercambio da prioridad al objetivo activo y a las misiones del paso del otro jugador. Con el avance automático activado, el paso continúa al recibir las confirmaciones necesarias, sin pulsar «Saltar». Las misiones pendientes o los datos desconocidos siguen esperando; el progreso del amigo no se copia al propio.

El pie del panel distingue entre datos pendientes de sincronizar y una acción pendiente del compañero; al pasar el ratón muestra el motivo. Si tu visita ya está resuelta, la flecha explica la espera en vez de indicar que faltan coordenadas. Las entregas pendientes conservan el destino del NPC.

En Dúo puedes pulsar **Sincronizar de nuevo**, o escribir `/rutaxp sincronizar`, para renovar los datos sin cambiar la guía, el progreso ni las opciones de ambos. Actualizad los dos con el mismo setup. Las pruebas reproducen el bloqueo con dos clientes simulados y verifican una ruta de entrega con el terreno incluido; falta confirmar el resultado en vuestra partida.

## Contenido conservado

- 57 rutas de misiones para los niveles 1–60: 29 de Alianza y 28 de Horda, con 2.343 pasos y 7.455 objetivos. Incluyen los inicios clásicos y Skyborne en ambas facciones, con variantes de clase.
- Interfaz de Antigravity, panel compacto, iconos, flecha facetada con giro continuo y posiciones de ventanas por personaje.
- 36 planes de talentos y sus 1.836 puntos, selector de builds y asistente del instructor. Las recomendaciones orientan al usuario; no compran habilidades ni gastan talentos por sí solas.
- Búsqueda, filtros, opcionales, confirmación manual, datos y progreso por personaje.

Las rutas proceden de Polestar/SendaFH y siguen en beta. Las pruebas de software no sustituyen recorrerlas dentro de Forever. Todavía requieren revisión de traducciones y del contenido que cambie en la beta, especialmente en los niveles 30–60.

## Plan de misiones y cambios de dirección (0.6.6)

El panel muestra una fila breve por misión que ya llevas y está prevista más adelante: contador, paso para hacerla y paso de entrega. La vista previa omite aceptaciones ya realizadas y trabajo que el juego confirma terminado. Las filas son informativas y respetan las condiciones del personaje, las marcas manuales y el modo de acompañar al amigo.

«En busca de calor» se acepta en el paso 37 de Dun Morogh, se hace en el 38 y se entrega en el 39. Su instrucción especifica recoger 14 leños de los troncos caídos junto al lago de Refugio Pinobruma. Una misión ya aceptada antes de ese punto muestra su planificación.

Las ramas alternativas cerradas en la aceptación también se omiten al llegar a su trabajo y entrega. Una misión que siga realmente en el diario conserva sus objetivos. El seguimiento de terreno reconoce los recortes de curvas ya recorridas, evitando acumular un retraso que hacía señalar puntos anteriores tras varias curvas.

La auditoría de estructura recorre las 57 guías y comprueba el orden y la continuidad por trayectoria, clase y raza. El informe conserva las limitaciones de las fuentes; no equivale a haber recorrido todas las misiones en el cliente.

## Altura del cliente y cálculo al caminar (0.6.5)

Forever puede devolver una altura nativa de `0` cuando no está disponible. Esa lectura se trata ahora como desconocida, como hace la compatibilidad de la fuente SendaFH. Antes podía rechazar rutas válidas por un supuesto cambio de piso al moverse y volver a calcular continuamente. El filtro se aplica solo a la altura leída del jugador; las alturas de destinos y mallas conservan su valor.

También se aplica al indicador vertical, los itinerarios capturados y los puntos de reunión nuevos. Una altura desconocida no confirma automáticamente un piso. `/rutaxp diagnostico` incluye las rutas aceptadas, rechazadas y el último motivo. Se añaden pruebas de movimiento con altura nativa cero, ausente e intermitente; la comprobación dentro del cliente sigue siendo necesaria.

## Panel compacto y seguimiento al caminar (0.6.4)

El panel recupera la presentación breve: objetivo, contador y una pista corta cuando aporta una acción necesaria. La vista previa vuelve a mostrar el NPC y el paso siguiente. Las explicaciones completas quedan en el tooltip al pasar el ratón, conservando los destinos corregidos.

El seguimiento conserva el recorrido seguro al recalcular y registra por dónde has pasado mientras espera una ruta, para no pedirte volver a curvas anteriores. Cambiar entre campamentos que sirven para el mismo objetivo no cancela continuamente el cálculo. Un cambio real de misión o paso sigue descartando la ruta anterior.

## Revisión de todas las guías (0.6.3)

Revisados los 7.444 objetivos de las 57 guías: se añaden destinos documentados para 422 objetivos y se explican otros 11 casos que necesitan objetos, una habilidad o acompañar a un NPC. Los vuelos señalan al maestro de salida; los objetivos ya terminados dejan de seleccionar sus posiciones. Las acciones de bolsa, piedra de hogar, nivel y notas explican qué hacer sin mostrar un error de coordenadas.

Cada objetivo tiene una instrucción en español. El panel conserva los contadores del juego y muestra las notas del paso y las mecánicas que antes quedaban ocultas. Los ocho objetivos de domesticación usan ese verbo; las conversaciones no se describen como combates. Se mantienen todas las acciones, condiciones, requisitos, cantidades, pasos y puntos anteriores.

Los detalles, fuentes y límites están en [INFORME_GUIAS.md](INFORME_GUIAS.md). La revisión de datos no equivale a recorrer todas las rutas en el cliente. Las dos misiones de cajas con instrucciones contradictorias en la fuente lo indican y remiten a los materiales de la caja y al requisito del registro; no inventan un lugar de recogida.

## Cálculo al caminar y misión de Cocina (0.6.2)

Las pequeñas variaciones de un marcador del juego ya no cancelan el cálculo pendiente. La identidad del objetivo se mantiene aunque sus coordenadas procedan del juego, de la guía o de una posición aprendida. Un cambio real de misión, giro o destino sigue provocando un cálculo nuevo. La tolerancia se mide desde el destino usado para calcular, de modo que un desplazamiento gradual tampoco se pierde.

Si un cálculo queda pausado por combate, la flecha explica esa espera y continúa al salir. `/rutaxp diagnostico` muestra su estado, número de cálculos y cancelaciones. Las pruebas con el motor y terreno incluidos simulan carrera y variaciones del marcador entre fotogramas; queda pendiente comprobar el resultado jugando en el cliente.

«Acampada para novatos: cocinar», en Kharanos, señala a Gremlock Pilsnor y explica que hay que hablar con él y aprender Cocina. Se conserva la confirmación real de la misión; llegar al instructor no la completa.

## Corrección del seguimiento de la flecha (0.6.1)

Al moverte durante el cálculo, la respuesta se engancha al tramo que ya estás recorriendo y conserva el avance entre segmentos contiguos. Pasar ligeramente al lado de un giro o recortar una esquina deja de mantener la flecha dirigida al punto anterior. Si retrocedes detrás de una esquina ya pasada, busca de nuevo desde donde estás. Los cálculos nuevos esperan a aterrizar si estás cayendo.

Los giros usan la posición del personaje y los puntos de terreno en el mismo sistema de coordenadas; los marcadores del mapa conservan su destino normal. Las pruebas recorren el camino entero de Gozwin a velocidad de carrera con retraso de cálculo, deriva lateral y variaciones de altura, además de pasillos de vuelta y pisos superpuestos. El progreso y las opciones del panel se conservan.

## Flecha por el terreno (0.6.0)

La flecha calcula un recorrido a pie y señala sus giros para rodear laderas y acceder por los pasos transitables de los datos incluidos. La distancia que muestra corresponde al recorrido pendiente. Viene activado; no hace falta instalar otro addon. También se aplica al acompañar al amigo y a las recogidas del modo dúo.

El cálculo utiliza el motor GPL de **Shortest Path Forever**, de Cillian Berragan, y las mallas publicadas por **Polestar/SendaFH** para Reinos del Este, Kalimdor y Zephras. La malla incluida corresponde al cliente Forever 1.60.1.70374. El paquete conserva la licencia, créditos y procedencia en `RutaXP/Pathing/`. El terreno de una beta puede cambiar; no se da por verificado un trayecto que el motor no pueda encontrar ni una fase cuyas coordenadas no coincidan.

Mientras calcula se muestra ese estado. Si te apartas del recorrido, lo calcula de nuevo desde tu posición; al cambiar de objetivo descarta el resultado anterior. Los cálculos nuevos esperan a salir de combate. Si falta cobertura, muestra **Dirección orientativa**; si el cálculo falla, explica que no tiene un camino comprobado. `/rutaxp recalcular` vuelve a intentarlo y `/rutaxp camino` permite activar o desactivar el seguimiento por terreno.

Los accesos publicados siguen teniendo prioridad: se conserva una entrada necesaria aunque esté lejos o el NPC esté cerca al otro lado de la montaña. Confirmar un acceso sirve para los objetivos siguientes de esa visita y también al ayudar al compañero. Entradas sin altura comprobada y transportes continúan requiriendo confirmación. Llegar a un giro, puerta o cueva nunca completa una misión ni copia el progreso del amigo.

## Panel ampliable y más misiones (0.5.1)

Pon el ratón sobre un borde o una esquina del panel compacto y arrastra con el botón izquierdo. El ancho y el alto se guardan por personaje, también al usar `/reload`. Los textos aprovechan el ancho nuevo y los controles permanecen accesibles. Para mover el panel completo sigue arrastrando su cabecera.

El paso actual ya puede mostrar todos sus objetivos, sin el límite anterior de seis. Al redimensionar aparece **Próximas misiones · vista previa**, con hasta doce acciones de los pasos siguientes y sus condiciones de raza/clase. Ampliar la altura deja ver más filas a la vez; la rueda permite recorrer lo que no quepa. Las próximas misiones son informativas: pulsarlas no omite pasos, cambia la flecha ni modifica el progreso. En acompañamiento dúo se utiliza el personaje de referencia.

## Configuración automática al formar grupo (0.5.0)

Instalad **0.5.0 o posterior los dos**, entrad con personajes de la misma facción y formad un grupo de dos. **Automático al agruparse** viene activado, también al actualizar desde versiones anteriores: descubre al compañero, acuerda una guía compatible con los datos disponibles y activa el avance automático con espera. No hace falta escribir comandos ni elegir un líder. El panel Dúo explica si está buscando al compañero, comprobando una ruta o esperando datos.

El personaje adelantado ve el paso del rezagado y la flecha señala el objetivo pendiente de ese amigo cuando hay coordenadas comprobadas. Su cursor real, sus confirmaciones y sus omisiones permanecen guardados. Mientras acompaña, los botones de avanzar, retroceder y omitir están bloqueados para evitar modificar por error un paso propio posterior. Cuando el amigo lo alcanza, ambos continúan desde su progreso real. Cada uno acepta, completa y entrega sus propias misiones.

La selección se confirma entre los dos addons; recibir un paso del amigo nunca lo convierte en progreso propio. Si traíais guías diferentes, solo se acuerda una ruta cuando las misiones y requisitos conocidos permiten comprobar una entrada común. Los inicios de raza o clase pueden necesitar progreso individual antes de coincidir. Los datos ocultos o caducados se explican como desconocidos y no cuentan como misiones terminadas. Una recuperación de requisitos sigue siendo individual.

Al salir del grupo se restauran las opciones de avance y espera que tenías antes, conservando la guía elegida y todo el progreso real. Las revisiones previas se apartan durante el acuerdo y se recuperan al salir si ese cursor no ha avanzado. La sesión automática también admite `/reload` y vuelve a comprobar al compañero. Grupos mayores, bandas, facciones distintas y compañeros con versiones anteriores no activan un acuerdo automático.

Para desactivarlo usa **Dúo → Progreso → Automático al agruparse** o `/rutaxp autoduo`; vuelve a usarlo para reactivarlo. Elegir manualmente otra guía o cambiar las opciones de dúo/espera pasa a control manual, para respetar tu decisión. Las herramientas anteriores siguen disponibles.

## Mejoras para jugar con un amigo (0.4.0)

En **Dúo y herramientas de ruta → Dúo** hay seis páginas: Progreso, Ruta común, Diferencias, Reunión, Partida y Paradas. En 0.5.0 la configuración automática se ocupa de la guía y la espera; podéis desactivarla y usar estos controles manualmente.

1. **Contadores exactos:** compara cantidades reales de cada objetivo, por ejemplo «tú 5/8 · amigo 3/8», también en las filas del panel compacto cuando el objetivo tiene índice. Los datos que el cliente no ofrece o que han caducado se muestran como desconocidos; no se convierten en ceros ni completados.
2. **Ruta común:** propone hasta tres rutas compatibles con nivel, raza, clase, facción y misiones conocidas de ambos. Da prioridad a lo que podéis continuar juntos y explica los requisitos de entrada. Cada uno confirma su propia selección, conservando sus cursores y marcas. No da por completado el principio de una guía por encontrar una misión común más adelante.
3. **Diferencias explicadas:** indica quién necesita aceptar una misión, terminar un objetivo o resolver una previa, con el NPC y los requisitos disponibles en las guías. «Ver destino» sirve para una recogida local con fuente suficiente; no mueve al compañero ni inventa requisitos desconocidos. Puedes volver al objetivo normal de la guía.
4. **Reunión:** permite compartir vuestra posición como punto acordado. Cada uno elige si quiere seguirlo con la flecha. Los avisos ayudan al separaros, cambiar de zona o morir; no afirman conocer una capa del mundo que la API no permita comprobar. El punto de reunión no completa misiones.
5. **Partida conjunta:** conserva hasta veinte puntos de partida por personaje, asociados a la pareja. Puedes guardarlos, consultar lo que le falta a cada uno y retomar tu guía tras jugar por separado. Conserva el progreso que hayas ganado: nunca copia el cursor, las omisiones ni las entregas del amigo. El guardado periódico solo se realiza con datos de una pareja confirmada.
6. **Paradas coordinadas:** propone vender, reparar, descansar o revisar al instructor usando los datos disponibles de bolsas, equipo, maná y niveles. Puedes anunciar una parada y marcarte listo. Son propuestas: no compran, reparan ni gastan recursos automáticamente, ni obligan al compañero a cambiar de ruta.

La comparación usa únicamente datos recientes que comparten vuestros addons por PARTY. El protocolo tiene límites de tamaño, frecuencia y caché, y rechaza datos de otros grupos o versiones incompatibles. La información guardada para retomar la partida es una referencia histórica, no prueba del estado actual del registro del amigo.

## Dúo y herramientas de ruta

Abre el botón **Dúo y herramientas de ruta** de la biblioteca, o `/rutaxp herramientas`.

- **Dúo:** sirve para dos personajes de la misma facción, de cualquier raza y clase. Ambos instaláis esta versión y formáis grupo. Muestra las misiones del paso, si las lleva el amigo, objetivos terminados y si está preparado. «Elegir la guía del amigo» conserva TU progreso: no copia su paso ni sus omisiones. `/rutaxp duo` permite controlarlo manualmente.
- **Esperar al amigo:** se activa con el acuerdo automático y se puede cambiar manualmente con `/rutaxp esperar`. Retiene el avance de los pasos compartidos hasta que ambos tengan los objetivos listos. No exige que ambos entreguen primero, ni espera las misiones de clase/raza que no se apliquen al compañero, ni las recuperaciones individuales. Puedes desactivarla para seguir por tu cuenta. La falta de datos recientes se muestra como desconocida. Las marcas de preparado son informativas.
- **Mediciones:** XP observada, XP por hora activa estimada, tiempo sin AFK ni pausa, recorrido terrestre estimado, muertes y duración observada de misiones y pasos. El informe se puede copiar. Empezar otra sesión conserva hasta 20 anteriores. Los avisos de atasco y mucho viaje necesitan muestras suficientes; no se da por optimizada una ruta ni se eliminan cadenas automáticamente.
- **Bloqueos:** explica nivel, misión abandonada y requisitos previos. Si encuentra una cadena completa en las guías incluidas, propone una recuperación temporal. Guarda tu punto y vuelve tras entregas reales, o al cancelar. El avance automático sigue respetando lo que hayas completado. Los requisitos sin fuente suficiente se explican sin inventar NPC o coordenadas.
- **Ajustar ruta:** propone alternativas según nivel, raza, clase, zona y registro. Con un dúo sincronizado usa el nivel menor como referencia y recuerda los inicios o misiones individuales. Los cambios son explícitos y se puede volver a la selección anterior.
- **Flecha con puntos:** incluye 15 itinerarios con 23 puntos: siete entradas de cuevas, el paso Durotar–Baldíos en ambos sentidos, el barco Trinquete–Bahía del Botín, el zepelín Orgrimmar–Entrañas y los portales Darnassus–Rut’theran. Los transportes incluyen ambos sentidos y se activan solo en los recorridos compatibles. Se pueden pausar, confirmar, omitir y reiniciar sin completar misiones. También puedes guardar posiciones propias, incluidas paradas de transporte. Las entradas sin altura verificada y los transportes requieren confirmación; un punto propio con altura compatible avanza al llegar. La cobertura es parcial, no un cálculo universal de caminos seguros.

Las mediciones quedan en los SavedVariables de tu personaje, sin servidor externo. El modo dúo solo intercambia por el canal de addon PARTY datos de ruta, nivel, clase, raza y estado de las misiones del paso, con mensajes limitados. No manda mensajes de chat visibles ni cambia el personaje del amigo. Si Forever restringe esa comunicación, lo indica y utiliza la información básica de misiones que permita el juego; no inventa su progreso. Grupos de más de dos y bandas suspenden la sincronización.

Cada uno debe aceptar y entregar sus misiones. Algunos objetos y misiones de clase son individuales. Razas iniciales distintas pueden necesitar terminar sus inicios y acordar un encuentro; el addon no inventa un trayecto común. Ser dos no garantiza poder derrotar cualquier élite.

## Correcciones conservadas

- Una misión posterior entregada ya no hace saltar cadenas o misiones anteriores pendientes. Las misiones grises se conservan por defecto, incluidos requisitos de clase.
- Cruzar una zona no cambia la guía seleccionada. `/reload` conserva la elección, los pasos en revisión y las posiciones guardadas.
- Se cargan y conservan las guías personales de versiones anteriores. Los registros que no puedan cargarse permanecen guardados para recuperarlos.
- La automatización actúa sobre objetivos válidos del paso actual: respeta opcionales, requisitos, ramas y modo de revisión. Mantener **Shift** la pausa. Las recompensas que requieren elegir o cuyos datos no pueden leerse quedan para confirmación manual.
- Omitir una misión no equivale a entregarla ni cumple sus requisitos. Abrir un vendedor o instructor tampoco demuestra que hayas hecho la tarea: confirma esas acciones en el panel cuando termines.
- La flecha sigue el objetivo actual y elige candidatos cercanos compatibles con tu clase, facción y mapa. No reutiliza posiciones de NPC sin verificar o de otro build. Los destinos de viaje con altura conocida requieren también una altura compatible para completar la llegada.
- Las acciones sin coordenadas muestran ese estado; no se apunta a otro NPC de un objetivo posterior. La flecha indica dirección y distancia y utiliza los puntos intermedios disponibles. Sigue también las instrucciones de la ruta en los tramos sin cobertura.
- El instructor diferencia cada rango y servicio y limpia sus marcas al cambiar de instructor. No compara puntos de mascota con oro. Si el árbol de talentos no puede leerse o ha cambiado, el panel mantiene las guías como referencia y evita mostrar puntos disponibles ficticios.
- Los instaladores seleccionan un único cliente de Forever, verifican todos los archivos y conservan una copia anterior antes de actualizar. Un fallo durante la activación restaura esa copia.

## Instalación

1. Descarga y descomprime `RutaXP-0.7.12.zip` desde [Releases](https://github.com/Dekaz4/RutaXP/releases/latest).
2. Ejecuta `Instalador_RutaXP.exe` o `Instalar_RutaXP.bat` y selecciona tu cliente de **WoW Forever**. También puedes copiar manualmente la carpeta `RutaXP` a su `Interface/AddOns`.
3. Comprueba que existe `Interface/AddOns/RutaXP/RutaXP.toc`.
4. Reinicia WoW si has añadido el addon por primera vez; una recarga no detecta carpetas nuevas. Actívalo en Accesorios y escribe `/rutaxp`.

El instalador no modifica `WTF` ni los archivos SavedVariables. La copia de la instalación anterior queda en una carpeta `.RutaXP.backup.*` junto a `RutaXP`, y el instalador muestra su ubicación. El paquete requiere `manifest.sha256`; si editas los archivos, reconstruye el paquete antes de usar el instalador.

Las copias locales de desarrollo no se distribuyen. Las copias creadas por el instalador contienen el addon; el progreso sigue guardado por el juego en `WTF`.

## Comandos

| Comando | Acción |
| --- | --- |
| `/rutaxp` o `/rutas` | Abre o cierra la biblioteca |
| `/rutaxp herramientas` | Abre Dúo, Mediciones, Bloqueos, Ajustar ruta y Flecha |
| `/rutaxp autoduo` | Activa o desactiva la configuración automática al formar grupo |
| `/rutaxp duo` | Pasa a control manual y activa o desactiva el modo dúo |
| `/rutaxp esperar` | Activa o desactiva esperar al compañero |
| `/rutaxp listo` | Cambia tu marca de preparado |
| `/rutaxp comun` | Rutas comunes; `comun 1` elige la primera para tu personaje |
| `/rutaxp diferencias` | Qué le falta a cada uno; `diferencia 1` enfoca un destino disponible |
| `/rutaxp reunion` | Punto compartido; `reunion marcar`, `seguir`, `cancelar` o `borrar` |
| `/rutaxp partida` | Partida conjunta; `partida guardar` y `partida reanudar` |
| `/rutaxp paradas` | Propuestas; `parada 1` inicia la primera y `parada fin` termina la tuya |
| `/rutaxp sesion` | Muestra mediciones y permite copiar el informe |
| `/rutaxp pendientes` | Retoma los objetivos pendientes de tu diario en la guía actual |
| `/rutaxp recuperar` | Explica bloqueos; `recuperar 1` inicia la primera recuperación propuesta |
| `/rutaxp volver` | Cancela la recuperación y vuelve a la ruta guardada |
| `/rutaxp adaptar` | Muestra propuestas de ruta |
| `/rutaxp puntos` | Controles de los puntos intermedios |
| `/rutaxp camino` | Activa o desactiva la flecha que sigue el terreno |
| `/rutaxp recalcular` | Busca otra vez el camino desde tu posición |
| `/rutaxp punto Entrada` | Guarda tu posición para este objetivo; reanuda desde el panel cuando termines de añadir puntos |
| `/rutaxp zona` o `/rutaxp recomendada` | Selecciona explícitamente una ruta recomendada para tu personaje y zona |
| `/rutaxp flecha` | Muestra u oculta la flecha |
| `/rutaxp mapa` | Coloca un marcador del destino actual en el mapa |
| `/rutaxp precision` | Muestra de dónde proceden las coordenadas |
| `/rutaxp siguiente` | Confirma una acción manual u omite el objetivo actual |
| `/rutaxp anterior` | Revisa el paso anterior |
| `/rutaxp talentos` | Abre el panel de talentos; también está disponible desde la interfaz y la tecla N |
| `/rutaxp diagnostico` | Muestra guía, paso, estado del objetivo, mapa y fuente de coordenadas para diagnosticar un error en juego |
| `/rutaxp version` | Muestra versión, build, interfaz y proyecto del cliente |
| `/rutaxp actualizar` | Muestra la versión del addon y el enlace al setup |

## Pruebas y reconstrucción

Se ejecuta el Lua real en LuaJIT/Lua 5.1 con API simulada. Los instaladores se prueban mediante sus helpers en carpetas temporales, sin instalar en un cliente real.

```powershell
python -m pip install lupa
python -m unittest discover -s tests -v
```

Las pruebas incluyen intercambio entre dos clientes Lua aislados (solo en simulación), sesiones con AFK, pausas, recargas y subida de nivel, recuperación de cadenas y puntos intermedios; además de recorridos simulados de Elwynn y Durotar, requisitos y variantes de clase, omisiones manuales, diálogos de misión, mapas y alturas, rangos del instructor, talentos y actualización con fallo y restauración. Sigue pendiente validar esta revisión dentro del cliente de Forever.

La suite también comprueba contadores y puntos de reunión entre clientes Lua aislados, compatibilidad de rutas para ambos perfiles, diferencias sin datos inventados, puntos de partida por pareja y propuestas de parada. No se ejecuta el juego como parte de estas pruebas.

Las pruebas automáticas de grupo cargan el TOC completo en dos clientes Lua aislados: descubrimiento sin comandos, acuerdo de guía, acompañamiento sin modificar el cursor propio, salida/reentrada, recarga, desactivación, revisiones y compatibilidad con versiones anteriores.

Las pruebas del panel simulan el arrastre nativo de sus ocho bordes/esquinas, tamaños guardados, reflujo del texto, límites de pantalla, rueda y actualización de la fila dúo. Las vistas previas se comprueban sin ejecutar automatización de misiones.

La navegación carga en pruebas el motor y la malla reales: el caso Dun Morogh 31,2/67,9 → campamento de Gozwin 27,27/62,86 obtiene un camino con giros que rodea la ladera. También se comprueban búsquedas canceladas, datos ausentes, entradas lejanas, memoria entre objetivos y acceso en acompañamiento dúo. Esta comprobación de datos y código no sustituye validar la ruta dentro del cliente.

Los puntos intermedios y sus fuentes se documentan en `RutaXP/Source/waypoints.json`; las coordenadas originales se conservan con su revisión y licencia.

Las rutas editables están en `RutaXP/Source/leveling.json`. Para regenerarlas:

```powershell
python RutaXP/Source/build_guides.py
```

Para reconstruir el manifiesto, el payload, el EXE y el ZIP en Windows, con el compilador de .NET Framework instalado:

```powershell
python tools/build_release.py
```

El constructor comprueba que los bytes del ZIP y del payload incrustado coinciden con los archivos del addon. No ejecuta el instalador ni copia nada en WoW.

Para verificar o regenerar el motor y los datos terrestres desde el checkout fijado `.sources/SendaFH`:

```powershell
python tools/vendor_pathing.py --check
python tools/vendor_pathing.py
```

El script comprueba los hashes originales y adapta únicamente nombres, el namespace privado y la guarda de compatibilidad. No modifica los algoritmos ni el contenido comprimido de los mapas.

## Créditos y licencias

Rutas de **Polestar**, por Fitz y colaboradores, adaptadas al español por **SendaFH / Forever Hispano**: [fuente y créditos](https://github.com/julen92/SendaFH). Se conservan el snapshot editable, la procedencia fijada y los avisos GPL y de los datos en `RutaXP/Licenses/`, incluidos los avisos del paquete de nombres españoles. Las mejoras de interfaz, navegación, talentos e instructor incorporadas por Antigravity se mantienen en esta revisión.

Motor terrestre de **Cillian Berragan / Shortest Path Forever**, versión 1.16.0, commit `b1ad5bd4bf579c781937af0e25f5233cc94b3726`, GPL-3.0-or-later: [fuente](https://github.com/cjber/shortest-path-forever). Mallas y adaptación procedentes de Polestar/SendaFH, commit `5d207e28e82e2c529143b21ace74fe88692f0067`; se conservan `LICENSE`, `CREDITS.md`, `PACK.json`, `UPSTREAM.json` y el manifiesto de adaptación `VENDORED.json` en `RutaXP/Pathing/`.
