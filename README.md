# RutaXP para WoW Forever

RutaXP 1.2.0 recupera los 57 capítulos de leveo de **RutaXP 0.7.36**. El panel de pasos y la brújula usan la interfaz de tu copia de Journey. OpenMap, el diario de mazmorras y la guía de talentos se abren desde el mismo addon.

## Actualizar

Con WoW cerrado, abre **Instalador_RutaXP.exe** y elige **Instalar o actualizar**. El instalador conserva una copia recuperable en `RutaXP-Suite-Backups`, dentro de la carpeta del cliente. Para montar la suite utiliza tus copias locales de OpenMap, ForeverDungeonJournal y Journey, incluidas las que el instalador anterior guardó allí. Los 29 capítulos de Alianza y los 28 de Horda vienen con RutaXP.

Si ya tienes un paquete personal preparado, puedes instalarlo sin conexión con **Instalar_RutaXP_Personal.exe**. Para restaurar la instalación anterior, cierra WoW y ejecuta `Instalar_RutaXP_Personal.exe --restore`.

## En el juego

| Acción | Acceso |
| --- | --- |
| Abrir el menú del addon | `/rutaxp` |
| Elegir un capítulo o configurar el seguimiento | Pulsa el título del panel de Journey o escribe `/rutaxp guias` |
| Mostrar u ocultar el panel de pasos | `/rutaxp guia` |
| Mostrar u ocultar la brújula | `/rutaxp flecha` |
| Elegir el capítulo recomendado para la zona, el nivel y el diario actuales | `/rutaxp zona` |
| Consultar las opciones del dúo | `/rutaxp herramientas` |
| Abrir el mapa de OpenMap | **M** o `/rutaxp mapa` |
| Abrir el diario de mazmorras | `/dj` o `/rutaxp mazmorras` |
| Retomar la preparación de una mazmorra aplazada | `/rutaxp plan` |
| Volver a una mazmorra por libre | `/rutaxp repetir Nombre de la mazmorra` |
| Ver los talentos y habilidades de tu clase | **N** o `/rutaxp talentos` |

El panel toma los pasos, los requisitos de misión, las opciones de grupo y los tramos de viaje del motor de RutaXP. Si tienes un capítulo guardado, el addon recupera el avance de ese personaje y comprueba su diario. Un personaje nuevo recibe una recomendación por zona, nivel y facción. En modo dúo cada personaje conserva su propio paso, incluso cuando ayuda a su compañero en uno anterior.

Los filtros de seguimiento del minimapa y de OpenMap comparten selección. Al pulsar **M** puedes ver los servicios de tu facción en la zona que consultas, a cualquier distancia. Las entradas de mazmorra respetan la acción configurada en OpenMap. Para una instalación nueva, el clic abre el diario.

### Misiones de mundo y mazmorras

Journey muestra la misión que estás siguiendo en el juego o en la que acaba de subir un contador. Para las mazmorras, RutaXP relaciona las misiones del capítulo con las guías oficiales de RestedXP disponibles, el diario de mazmorras y los requisitos de Forever. En un mismo panel ves las previas, las recogidas exteriores y las que solo puedes aceptar dentro.

Pulsa **Preparar mazmorra** para seguir las recogidas con la brújula. También reconoce una recogida al pasar cerca. Si prefieres seguir solo, pulsa **Seguir con la ruta de mundo abierto**. Al salir con los objetivos de la visita completos, la guía conserva las entregas pendientes. Las visitas posteriores quedan a tu elección. El diario activa el modo **Gamer** al actualizar cada personaje y respeta los cambios que hagas después en sus opciones.

## Preparar el paquete local

Desde la raíz del proyecto y con Python 3.10 o posterior, indica la carpeta de accesorios de WoW Forever.

```powershell
python tools/build_personal_suite.py --addons 'E:\WOW\World of Warcraft\_forever_\Interface\AddOns'
python tools/verify_personal_suite.py dist/RutaXP-1.2.0-personal.zip --addons 'E:\WOW\World of Warcraft\_forever_\Interface\AddOns'
```

Los créditos y las licencias se encuentran en [NOTICE.md](NOTICE.md) y en `RutaXP/Licenses`.
