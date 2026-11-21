# RutaXP para WoW Forever

RutaXP reúne el mapa, el diario de mazmorras, las guías oficiales de RestedXP y los talentos en una sola carpeta `Interface/AddOns/RutaXP`. La biblioteca abre las guías desde RutaXP. Si tienes Journey, el instalador incorpora su panel de pasos y su brújula al paquete personal.

## Instalar el paquete personal

Cierra WoW y ejecuta **Instalar_RutaXP_Personal.exe**. Comprueba la carpeta que muestra el instalador. Este ejecutable contiene el paquete ya preparado y sirve también sin conexión. Al volver a la selección de personajes, abre **Accesorios** y comprueba que **RutaXP** está activado para el personaje con el que vas a jugar.

El instalador comprueba el paquete antes de sustituir RutaXP. Guarda las instalaciones anteriores en `RutaXP-Suite-Backups`, dentro de la carpeta del cliente. Aparta también la copia separada de Journey cuando el paquete incluye su interfaz. Conserva el progreso de cada personaje y tus elecciones de talentos. Para restaurar los addons anteriores, cierra WoW y ejecuta `Instalar_RutaXP_Personal.exe --restore`.

## Preparar el paquete en otro ordenador

En el menú de **Instalador_RutaXP.exe**, elige **Instalar o actualizar**. El instalador prepara la suite para tu cliente con tus copias locales de OpenMap, ForeverDungeonJournal y, si está disponible, Journey. Verifica la edición oficial de RestedXP con SHA-256. También puedes ejecutar **Instalar_Suite_RutaXP.exe** directamente.

## En el juego

| Acción | Cómo abrirla |
| --- | --- |
| Menú de RutaXP | `/rutaxp` o el menú de accesorios |
| Mapa de OpenMap | **M** o `/rutaxp mapa` |
| Diario de mazmorras | `/dj` o `/rutaxp mazmorras` |
| Buscar y elegir una guía | `/rutaxp guias` o el título del panel de Journey |
| Mostrar u ocultar los pasos y la brújula | `/rutaxp guia` |
| Volver al seguimiento automático | **Seguir mi zona** o `/rutaxp zona` |
| Guía de talentos y habilidades de RutaXP | **N** o `/rutaxp talentos` |

Las casillas de seguimiento de la lupa del minimapa y del panel de OpenMap comparten la misma selección. Pulsa **M** y elige una zona para ver los servicios de tu facción a cualquier distancia, también con el registro de misiones abierto. Por ejemplo, al marcar **Reparación** puedes ver a **Durnan Cortapieles** en el Valle de Crestanevada, en Dun Morogh. Los instructores de clase corresponden a la clase de tu personaje. Al activar **Misiones de nivel bajo**, el mapa muestra las ofertas que el cliente comunica para cada zona.

Una instalación nueva abre el diario al pulsar una entrada de mazmorra en OpenMap. Si ya elegiste otra acción en OpenMap, el instalador conserva tu preferencia. En el panel de talentos puedes seguir consultando la distribución por nivel y las habilidades de tu clase. RestedXP se encarga del recorrido de leveo.

## Continuar con un personaje

Al entrar, RutaXP da prioridad a la guía y al paso que ya tenías activos en el motor de RestedXP. Para los capítulos antiguos de RutaXP compara las misiones del paso guardado con las del nuevo capítulo, la zona, el nivel y el diario de ese personaje. Los números de paso pertenecen a cada recorrido. El progreso del capítulo antiguo sigue guardado.

En modo automático, RutaXP consulta la zona al viajar. Puedes fijar otra guía en la biblioteca y volver al modo automático con **Seguir mi zona**. La biblioteca incluye las guías oficiales que el cliente considera compatibles con ese personaje. La edición incluida de Forever cubre zonas iniciales y contenidos específicos. Si tu zona y nivel carecen de una ruta oficial de leveo, el panel te avisa.

Si venías de un capítulo antiguo con el dúo activado, el panel **Misiones en curso** te permite acabar lo que ya habías empezado. Comprueba tu diario al entrar y da prioridad a las misiones de tu último paso. Pulsa el icono de una misión para abrir su ficha. Cuando jugáis juntos, **Activa para ambos** indica que el juego ve esa misión en los dos diarios. Cada personaje conserva su propio avance. Cuando termines ese grupo de misiones, RutaXP vuelve a buscar un capítulo. También puedes elegirlo antes en la biblioteca.

## Reconstrucción desde el código

Con Python 3.10 o posterior puedes generar el ZIP personal desde la raíz del proyecto.

```powershell
python tools/build_personal_suite.py --addons 'E:\WOW\World of Warcraft\_forever_\Interface\AddOns'
```

La composición lee los módulos locales y usa la revisión oficial de RestedXP registrada en `tools/suite_rested.py`. El ZIP se genera en `dist`. La instalación es independiente de la compilación.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/Install-Suite.ps1 -Client 'E:\WOW\World of Warcraft\_forever_' -Archive dist/RutaXP-1.1.0-personal.zip
```

La última versión de las antiguas rutas propias fue la [0.7.38](https://github.com/Dekaz4/RutaXP/releases/tag/v0.7.38). El índice de migración usa los mapas y los identificadores de misión de esos capítulos.
