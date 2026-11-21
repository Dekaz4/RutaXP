# RutaXP 1.0 para WoW Forever

RutaXP reúne OpenMap, Dungeon Journal, las guías oficiales de RestedXP y la guía de talentos de RutaXP. El paquete personal instala una sola carpeta `Interface/AddOns/RutaXP`. Cada módulo conserva su interfaz, sus datos y sus controles.

## Instalar el paquete personal

Cierra WoW y ejecuta **Instalar_RutaXP_Personal.exe**. Comprueba la carpeta que muestra el instalador. Este ejecutable contiene el paquete ya preparado y sirve también sin conexión. Al volver a la selección de personajes, abre **Accesorios** y comprueba que **RutaXP** está activado para el personaje con el que vas a jugar.

El instalador comprueba el paquete completo antes de sustituir la carpeta RutaXP. Retira de `Interface/AddOns` las tres instalaciones separadas y las copias de RutaXP que dejó el actualizador antiguo. Guarda la instalación anterior en `RutaXP-Suite-Backups`, dentro de la carpeta del cliente. Conserva tus elecciones de talentos y traslada los ajustes del mapa y del diario. RestedXP empieza con su biblioteca oficial y un perfil nuevo. Para volver a la instalación anterior, cierra WoW y ejecuta `Instalar_RutaXP_Personal.exe --restore`.

## Preparar el paquete en otro ordenador

En el menú de **Instalador_RutaXP.exe** 1.0.2, elige **Instalar o actualizar**. El instalador prepara y activa la suite en el cliente elegido. Usa las copias locales de OpenMap y ForeverDungeonJournal y verifica la versión oficial de RestedXP con SHA-256. También puedes ejecutar **Instalar_Suite_RutaXP.exe** directamente.

## En el juego

| Acción | Cómo abrirla |
| --- | --- |
| Menú de RutaXP | `/rutaxp` o el menú de accesorios |
| Mapa de OpenMap | **M** o `/rutaxp mapa` |
| Diario de mazmorras | `/dj` o `/rutaxp mazmorras` |
| Selector de guías oficiales de RestedXP | `/rutaxp guias` |
| Guía de talentos y habilidades de RutaXP | **N** o `/rutaxp talentos` |

Las casillas de seguimiento de la lupa del minimapa y del panel de OpenMap comparten la misma selección. Pulsa **M** y elige una zona para ver los servicios de tu facción a cualquier distancia, también con el registro de misiones abierto. Por ejemplo, al marcar **Reparación** puedes ver a **Durnan Cortapieles** en el Valle de Crestanevada, en Dun Morogh. Los instructores de clase corresponden a la clase de tu personaje. Al activar **Misiones de nivel bajo**, el mapa muestra las ofertas que el cliente comunica para cada zona.

Una instalación nueva abre el diario al pulsar una entrada de mazmorra en OpenMap. Si ya elegiste otra acción en OpenMap, el instalador conserva tu preferencia. En el panel de talentos puedes seguir consultando la distribución por nivel y las habilidades de tu clase. RestedXP se encarga del recorrido de leveo.

## Reconstrucción desde el código

Con Python 3.10 o posterior puedes generar el ZIP personal desde la raíz del proyecto.

```powershell
python tools/build_personal_suite.py --addons 'E:\WOW\World of Warcraft\_forever_\Interface\AddOns'
```

La composición lee los módulos locales y usa la revisión oficial de RestedXP registrada en `tools/suite_rested.py`. El ZIP se genera en `dist`. La instalación es independiente de la compilación.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/Install-Suite.ps1 -Client 'E:\WOW\World of Warcraft\_forever_' -Archive dist/RutaXP-1.0.2-personal.zip
```

La última versión de las antiguas rutas propias fue la [0.7.38](https://github.com/Dekaz4/RutaXP/releases/tag/v0.7.38). Sus datos se mantienen en el historial del proyecto. El paquete personal usa únicamente la guía de talentos de aquella versión.
