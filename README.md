# RutaXP 1.0 para WoW Forever

RutaXP reúne OpenMap, Dungeon Journal, las guías oficiales de RestedXP y la guía de talentos de RutaXP. El paquete personal instala una sola carpeta `Interface/AddOns/RutaXP`. Cada módulo conserva su interfaz, sus datos y sus controles.

## Instalar el paquete personal

Cierra WoW y ejecuta **Instalar_RutaXP_Personal.exe**. Comprueba la carpeta que muestra el instalador. Este ejecutable contiene el paquete ya preparado y sirve también sin conexión. Al terminar, abre WoW y escribe **/rutaxp**.

El instalador aparta las copias anteriores de los addons y guarda una copia en `RutaXP-Suite-Backups` dentro del cliente. Conserva tus elecciones de talentos y traslada los ajustes del mapa y del diario. RestedXP empieza con su biblioteca oficial y un perfil nuevo. Tus guías importadas y tu progreso de la instalación separada permanecen en sus archivos originales. Para volver a la instalación anterior, cierra WoW y ejecuta `Instalar_RutaXP_Personal.exe --restore`.

## Preparar el paquete en otro ordenador

La distribución pública contiene el constructor para Windows. Ejecuta **Instalar_Suite_RutaXP.exe** con las copias locales de OpenMap y ForeverDungeonJournal. El constructor verifica la versión oficial de RestedXP con SHA-256. Si usas el antiguo **Instalador_RutaXP.exe**, al actualizar encontrarás el constructor en `Interface/AddOns/RutaXP/Instalar_Suite_RutaXP.exe`. Ejecútalo con WoW cerrado para completar la transición al addon único. Usa el instalador personal o el constructor de la suite para las siguientes actualizaciones.

## En el juego

| Acción | Cómo abrirla |
| --- | --- |
| Menú de RutaXP | `/rutaxp` o el menú de accesorios |
| Mapa de OpenMap | **M** o `/rutaxp mapa` |
| Diario de mazmorras | `/dj` o `/rutaxp mazmorras` |
| Selector de guías oficiales de RestedXP | `/rutaxp guias` |
| Guía de talentos y habilidades de RutaXP | **N** o `/rutaxp talentos` |

Una instalación nueva abre el diario al pulsar una entrada de mazmorra en OpenMap. Si ya elegiste otra acción en OpenMap, el instalador conserva tu preferencia. En el panel de talentos puedes seguir consultando la distribución por nivel y las habilidades de tu clase. RestedXP se encarga del recorrido de leveo.

## Reconstrucción desde el código

Con Python 3.10 o posterior puedes generar el ZIP personal desde la raíz del proyecto.

```powershell
python tools/build_personal_suite.py --addons 'E:\WOW\World of Warcraft\_forever_\Interface\AddOns'
```

La composición lee los módulos locales y usa la revisión oficial de RestedXP registrada en `tools/suite_rested.py`. El ZIP se genera en `dist`. La instalación es independiente de la compilación.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/Install-Suite.ps1 -Client 'E:\WOW\World of Warcraft\_forever_' -Archive dist/RutaXP-1.0.0-personal.zip
```

La última versión de las antiguas rutas propias fue la [0.7.38](https://github.com/Dekaz4/RutaXP/releases/tag/v0.7.38). Sus datos se mantienen en el historial del proyecto. El paquete personal usa únicamente la guía de talentos de aquella versión.
