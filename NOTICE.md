# Procedencia y licencias de RutaXP

El catálogo de recogidas anticipadas filtra datos de las misiones de Forever publicados por [Efficient Games](https://efficient.games) bajo [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). RutaXP selecciona identificadores y contrasta los objetivos, los temporizadores y las acciones al aceptar con [CMaNGOS Classic-DB](https://github.com/cmangos/classic-db), GPL-3.0. Las revisiones de origen están en `RutaXP/Licenses/PROVENANCE.txt`.

RutaXP y sus modificaciones se distribuyen bajo GPL-3.0-only; el texto está en `LICENSE`. Los componentes de terceros conservan sus propios avisos y, cuando corresponda, licencias adicionales.

- **Polestar**, por Fitz y colaboradores, y **SendaFH / Forever Hispano**: recorridos, traducciones, recursos gráficos de `RutaXP/Media` y datos adaptados desde [SendaFH](https://github.com/julen92/SendaFH), revisión `5d207e28e82e2c529143b21ace74fe88692f0067`. Se conservan sus avisos en `RutaXP/Licenses/`. El trabajo de integración e interfaz realizado con Antigravity se conserva; ese crédito no sustituye la autoría de los recursos originales.
- **Shortest Path Forever**, por Cillian Berragan: motor de rutas y mapa de Zephras Isle, GPL-3.0-or-later. Las mallas de los otros continentes y sus adaptaciones proceden de Polestar/SendaFH. Revisiones, huellas y créditos se incluyen en `RutaXP/Pathing/CREDITS.md`, `UPSTREAM.json`, `VENDORED.json`, `PACK.json` y `LICENSE`.
- **pfQuest**, por Shagu, MIT; **Ding!/DingDB**, por Yendi; datos de Blizzard, Carbonite y las demás fuentes: se mantienen sus avisos específicos en `RutaXP/Licenses/`, incluidos los del catálogo de nombres españoles y los datos de guías.
- **Servicios del mapa**. Las posiciones y funciones de los NPC y buzones proceden de pfQuest (MIT). Las posadas y los instructores de clase de Forever se contrastan con Polestar/SendaFH. La herramienta `tools/build_map_services.py` identifica las revisiones y reconstruye el catálogo. Los iconos se cargan desde el propio cliente de WoW.
- **EverythingQuests**, por Wheelbarrel00, y **AllTheThings WoW Addon**, ambos MIT: datos numéricos de disponibilidad y comprobación de cadenas de Forever. Las revisiones exactas, archivos, líneas y huellas se conservan en `RutaXP/Source/quest_requirements_evidence.json` y `guide_revisions.json`. Sus licencias completas se incluyen en `RutaXP/Licenses/EverythingQuests-MIT.txt` y `AllTheThings-MIT.txt`. No se importa su código de ejecución ni el texto narrativo de las misiones.
- **QuestieDB / Questie**: contraste de los nueve IDs de requisito de Holy Diver, con revisión fijada `21be34023b72cf2ec3027cb9a61a8b72a1910857` e incidencia pública Questie/Questie#8040. Se referencian hechos numéricos y su procedencia; no se importa código ni texto narrativo de esa base. Se conserva su aviso original en `RutaXP/Licenses/QuestieDB-NOTICE.md`, sin atribuirle una licencia MIT.

- **ForeverLevelingBiS**, por Thunder, MIT. Los datos de equipo y recompensas de Forever proceden de la versión 0.12.0-beta incluida en SendaFH. El aviso íntegro figura en `RutaXP/Licenses/ForeverLevelingBiS-MIT.txt`.

Los datos editables y las herramientas de reconstrucción acompañan al código. Los ejecutables de las publicaciones se compilan desde `tools/Installer.cs` y `tools/Updater.cs`. Las fuentes originales fijadas se identifican en los archivos de procedencia; no se publican las copias personales ni los archivos `WTF` de ningún jugador.

RutaXP es un proyecto independiente y no está afiliado a Blizzard Entertainment.
