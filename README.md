# RutaXP para WoW Forever

RutaXP 1.2.23 incluye los 57 capítulos de leveo de **RutaXP 0.7.36**. El panel de pasos, el selector de rutas, la brújula y el panel de talentos comparten el estilo de Journey. OpenMap, el diario de mazmorras y la guía de talentos se abren desde el mismo addon.

## Actualizar

Con WoW cerrado, abre **Instalador_RutaXP.exe** y pulsa **1**. Los instaladores desde la versión 1.0.2 reciben el constructor actualizado desde GitHub. Si conservas el ejecutable de la serie 0.7, 1.0.0 o 1.0.1, sustituye ese archivo una vez por [el instalador actual](https://github.com/Dekaz4/RutaXP/releases/latest/download/Instalador_RutaXP.exe). El instalador guarda las copias de recuperación fuera de la carpeta que actualiza Battle.net y traslada allí las copias anteriores. Si tienes el cliente en `E:\WOW\World of Warcraft\_forever_`, las encontrarás en `E:\WOW\RutaXP-Suite-Backups\World of Warcraft\_forever_`. Para montar la suite utiliza tus copias locales de OpenMap, Dungeon Journal y Journey, incluidas las de una instalación anterior. Si falta un módulo, la opción 1 descarga y verifica su paquete oficial. También busca los ZIP oficiales en la carpeta Descargas de Windows y en las carpetas configuradas en Chrome, Edge, Brave y Firefox, aunque estén en otra unidad. Si falla la descarga directa de uno de esos dos módulos, el instalador abre la página del autor y espera la descarga. Si el ZIP está en otra carpeta, al final de la espera puedes seleccionarlo en cualquier unidad. Los 29 capítulos de Alianza y los 28 de Horda vienen con RutaXP.

En un PC nuevo, termina de instalar WoW Forever en Battle.net. Si el instalador pide una ubicación, selecciona la carpeta `_forever_` de ese PC. La opción 1 prepara `Interface\AddOns` durante la primera instalación.

Desde la versión 1.2.12 del instalador, la opción 1 comprueba primero la versión. Si estás al día, termina sin descargar ningún paquete. Si tu versión tiene una actualización incremental, descarga y escribe solo los archivos modificados. La opción 2 verifica y repara la suite completa. Los ejecutables anteriores pueden descargar el paquete completo para iniciar el constructor actualizado.

La opción **1** también instala **LFG Forever** de Artefius con su paquete de idioma español. Ambos vienen con el instalador y aparecen por separado en la lista de accesorios de WoW. Entra con tu personaje y escribe **/lfg** para buscar grupo.

Si ya tienes un paquete personal preparado, puedes instalarlo sin conexión con **Instalar_RutaXP_Personal.exe**. Para restaurar la instalación anterior, cierra WoW y ejecuta `Instalar_RutaXP_Personal.exe --restore`.

## En el juego

Con el avance automático activado, RutaXP aprovecha objetivos del diario que quedan de camino en el capítulo actual. Puede sugerir terminar una cacería a medias, trabajar dos misiones con los mismos enemigos o entregar varias al pasar por un campamento. Journey explica la parada y conserva el progreso del capítulo.

| Acción | Acceso |
| --- | --- |
| Abrir el menú del addon | `/rutaxp` |
| Elegir un capítulo o configurar el seguimiento | Pulsa el título del panel de Journey o escribe `/rutaxp guias` |
| Mostrar u ocultar el panel de pasos | `/rutaxp guia` |
| Personalizar la brújula | Haz clic izquierdo sobre la flecha. Elige el diseño y el tamaño, o desmarca **Mostrar distancias**. Se guarda por personaje. |
| Mostrar u ocultar la brújula | `/rutaxp flecha` |
| Elegir el capítulo recomendado para la zona, el nivel y el diario actuales | `/rutaxp zona` |
| Consultar las opciones del dúo | `/rutaxp herramientas` |
| Abrir el mapa de OpenMap | **M** o `/rutaxp mapa` |
| Mostrar solo los puntos de interés de tu zona | **M → Filtros → Solo mi zona**. Se actualiza al cambiar de zona y se guarda por personaje. |
| Abrir el diario de mazmorras | `/dj` o `/rutaxp mazmorras` |
| Buscar grupo para una mazmorra | `/lfg` |
| Ver las misiones de mazmorra y retomar una preparación aplazada | Pulsa la llave del minimapa, elige la mazmorra o el ala y revisa sus misiones. **Preparar mazmorra** o **Retomar preparación** dirige la brújula a la siguiente misión. También puedes usar `/rutaxp plan`. |
| Volver a una mazmorra por libre | `/rutaxp repetir Nombre de la mazmorra` |
| Ver los talentos y habilidades de tu clase | **N** o `/rutaxp talentos` |

El panel toma los pasos, los requisitos de misión, las opciones de grupo y los tramos de viaje del motor de RutaXP. Si tienes un capítulo guardado, el addon recupera el avance de ese personaje y comprueba su diario. Un personaje nuevo recibe una recomendación por zona, nivel y facción. En modo dúo cada personaje conserva su propio paso, incluso cuando ayuda a su compañero en uno anterior.

Pulsa **M** y abre **Filtros** en la esquina superior derecha del mapa, junto al diario de misiones. Marca **Reparación**, **Tabernero** o los servicios que quieras ver en la zona que consultas, a cualquier distancia. El mapa y el minimapa comparten las casillas. Las entradas de mazmorra respetan la acción configurada en OpenMap. Para una instalación nueva, el clic abre el diario.

Los servicios se dibujan también en la primera apertura del mapa. En pueblos como Kharanos y Theramore, los iconos de distintos servicios se separan y el texto al pasar el ratón identifica a sus proveedores.

Si el objetivo está en otro continente, el panel de Journey indica cómo llegar al siguiente transporte. La brújula señala el muelle o el maestro de vuelo. Las conexiones observadas en el mapa de vuelo de ese personaje permiten incorporar vuelos al viaje. En la travesía de Menethil a Auberdine, la guía indica que permanezcas a bordo en Costasur y recupera el destino de misión al llegar. La flecha de misión es dorada y lleva dos marcas en la cola. Al liberar el espíritu señala el cadáver y al resucitar recupera el objetivo anterior. La brújula comparte la opción `/rutaxp flecha` y conserva la posición que ya habías elegido.

En los tramos a pie, la brújula señala un punto a media distancia para que puedas seguir la forma del sendero. Al acercarte al siguiente giro, apunta al cruce. Debajo solo aparecen los metros, por ejemplo **35 m / 240 m**. La primera cifra es la distancia al punto que señala la flecha y la segunda, lo que queda del recorrido. En el tramo final se muestra solo la distancia al destino. Mientras recalcula, conserva la indicación anterior si todavía sirve para ese trayecto. En los viajes entre zonas te guía hasta la salida por carretera y retoma la misión al cruzar.

### Misiones de mundo y mazmorras

Journey muestra la misión que estás siguiendo en el juego o en la que acaba de subir un contador. Para las mazmorras, RutaXP relaciona las misiones del capítulo con las guías oficiales de RestedXP disponibles, el diario de mazmorras y los requisitos de Forever. En un mismo panel ves las previas, las recogidas exteriores y las que solo puedes aceptar dentro.

Con una guía activa, el panel y la flecha siguen el paso actual. Si marcas otra misión en el diario o completas parte de ella por el camino, su progreso se guarda y la brújula sigue con el recorrido.

La guía puede sugerir una mazmorra cercana. Pulsa **Preparar mazmorra** para seguir sus recogidas con la brújula. Si prefieres volver al recorrido, pulsa **Seguir con la ruta de mundo abierto**. Al salir con los objetivos de la visita completos, la guía conserva las entregas pendientes. Las visitas posteriores quedan a tu elección. El diario activa el modo **Gamer** al actualizar cada personaje y respeta los cambios que hagas después en sus opciones.

## Preparar el paquete local

Desde la raíz del proyecto y con Python 3.10 o posterior, indica la carpeta de accesorios de WoW Forever.

```powershell
python tools/build_personal_suite.py --addons 'E:\WOW\World of Warcraft\_forever_\Interface\AddOns'
python tools/verify_personal_suite.py dist/RutaXP-1.2.23-personal.zip --addons 'E:\WOW\World of Warcraft\_forever_\Interface\AddOns'
```

Los créditos y las licencias se encuentran en [NOTICE.md](NOTICE.md) y en `RutaXP/Licenses`.
