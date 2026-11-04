local _, ns = ...

-- Rutas originales. Los niveles son aproximados: manda siempre el registro
-- de misiones y la dificultad que muestre el cliente de WoW Forever.

ns:RegisterGuide({
    id = "alliance_elwynn_1_10",
    title = "Elwynn: de Villanorte a Villadorada",
    faction = "Alliance",
    minLevel = 1,
    maxLevel = 10,
    kind = "Inicio",
    status = "orientativa",
    summary = "Recorrido orientativo de nivel 1-10 basado en Classic, pendiente de verificar en WoW Forever. Propone un orden por lugares; no es una guía completa misión por misión.",
    steps = {
        { title = "1. Revisa Villanorte", zone = "Bosque de Elwynn", text = "Recoge las tareas disponibles en tu punto de inicio y lee sus objetivos. Comprueba qué enemigos y objetos pide realmente Forever antes de salir de la abadía." },
        { title = "2. Haz un círculo corto", zone = "Bosque de Elwynn", text = "Agrupa los objetivos cercanos a la abadía y vuelve cuando puedas entregar varios juntos. Avanza hacia los viñedos o la mina solo si tu registro te lleva allí y la dificultad es adecuada." },
        { title = "3. Cierra la etapa de inicio", zone = "Bosque de Elwynn", text = "Entrega las tareas terminadas, vende lo que no necesites y revisa el instructor de tu clase si hay uno disponible. Conserva comida, agua si usas maná y espacio de mochila para el siguiente tramo." },
        { title = "4. Sigue el camino a Villadorada", zone = "Bosque de Elwynn", text = "Viaja por el camino principal y acepta las tareas que encuentres en Villadorada. Vincula aquí la piedra de hogar si el posadero ofrece esa opción." },
        { title = "5. Agrupa las granjas del sur", zone = "Bosque de Elwynn", text = "Si tienes objetivos en las granjas y sus alrededores, resuélvelos en una misma salida. No entres solo en una mina con enemigos más fuertes que tú: ganar un nivel fuera puede evitar un viaje de recuperación." },
        { title = "6. Recorre el este del bosque", zone = "Bosque de Elwynn", text = "Encadena las tareas disponibles junto a los lagos y el campamento maderero del este. Mantén una salida despejada cerca de los múrlocs, que pueden atraer más enemigos al huir." },
        { title = "7. Prepara Ventormenta", zone = "Bosque de Elwynn", text = "Regresa a Villadorada para entregar y ordenar la mochila antes de visitar Ventormenta. Aprovecha la ciudad para localizar instructores y servicios, y activa su ruta de vuelo cuando sea posible." },
        { title = "8. Elige el siguiente tramo", zone = "Bosque de Elwynn", text = "Al acercarte al nivel 10, termina las tareas asequibles de Elwynn que tengas a mano. Abre el itinerario de la Alianza para valorar Páramos de Poniente u otra zona según tu registro y el transporte disponible." },
    },
})

ns:RegisterGuide({
    id = "alliance_dun_morogh_1_10",
    title = "Dun Morogh: del valle a Forjaz",
    faction = "Alliance",
    minLevel = 1,
    maxLevel = 10,
    kind = "Inicio",
    status = "orientativa",
    summary = "Recorrido orientativo de nivel 1-10 basado en Classic, pendiente de verificar en WoW Forever. Los lugares sirven para ordenar viajes; confirma las tareas y sus requisitos en el cliente.",
    steps = {
        { title = "1. Explora el valle inicial", zone = "Dun Morogh", text = "Revisa los encargos del Valle de Crestanevada y de Yunquemar que estén disponibles para tu personaje. Separa mentalmente los objetivos de campo de los que exigen entrar en cuevas." },
        { title = "2. Completa primero el exterior", zone = "Dun Morogh", text = "Haz las tareas cercanas al campamento en una vuelta por el exterior. Evita perseguir enemigos hasta grupos nuevos y regresa a entregar cuando tengas varias tareas terminadas." },
        { title = "3. Decide cuándo entrar en la cueva", zone = "Dun Morogh", text = "Entra en una cueva únicamente si una tarea activa lo requiere y puedes afrontar a sus enemigos. Avanza poco a poco, observando las reapariciones que pueden cerrar el camino de vuelta." },
        { title = "4. Viaja a Kharanos", zone = "Dun Morogh", text = "Al terminar el valle, sigue la salida y el camino hacia Kharanos. Recoge los encargos del poblado, vende objetos y valora fijar allí la piedra de hogar." },
        { title = "5. Agrupa el entorno de Kharanos", zone = "Dun Morogh", text = "Combina las tareas del lago y de los alrededores del poblado que aparezcan en tu registro. Si te mandan en direcciones opuestas, completa primero un lado y vuelve por el otro." },
        { title = "6. Avanza hacia el este", zone = "Dun Morogh", text = "Reserva la zona de la cantera de Gol'Bolar para cuando sus enemigos sean de dificultad razonable. Lleva curación y busca compañía si el objetivo está rodeado o marcado como élite." },
        { title = "7. Haz una visita útil a Forjaz", zone = "Dun Morogh", text = "Agrupa una visita a Forjaz con entregas o entrenamiento que ya necesites. Localiza la ruta de vuelo y los servicios de tu clase antes de regresar al exterior." },
        { title = "8. Prepara Loch Modan", zone = "Dun Morogh", text = "Cerca del nivel 10, revisa las tareas pendientes del este y las que te indiquen viajar a otra zona. Consulta el itinerario de la Alianza y el mapa antes de tomar el paso hacia Loch Modan." },
    },
})

ns:RegisterGuide({
    id = "alliance_teldrassil_1_10",
    title = "Teldrassil: una vuelta por el gran árbol",
    faction = "Alliance",
    minLevel = 1,
    maxLevel = 10,
    kind = "Inicio",
    status = "orientativa",
    summary = "Recorrido orientativo de nivel 1-10 basado en Classic, pendiente de verificar en WoW Forever. El transporte y las misiones pueden variar; esta ruta no detalla cadenas completas.",
    steps = {
        { title = "1. Reúne las tareas de la cañada", zone = "Teldrassil", text = "Recorre el asentamiento inicial de Cañada Umbría y consulta los encargos disponibles. Lee dónde están los objetivos antes de alejarte de Aldrassil." },
        { title = "2. Limpia objetivos cercanos", zone = "Teldrassil", text = "Resuelve las tareas de los claros próximos en una misma vuelta. Mantén comida o agua a mano y vuelve a entregar cuando el viaje resuelva varias tareas a la vez." },
        { title = "3. Afronta los interiores con margen", zone = "Teldrassil", text = "Si una tarea te lleva a una cueva o edificio, comprueba primero el nivel de los enemigos de la entrada. Pide ayuda para objetivos difíciles y evita quedarte sin recursos lejos de una salida." },
        { title = "4. Baja a Dolanaar", zone = "Teldrassil", text = "Sigue el camino hasta Dolanaar cuando termines la etapa inicial. Recoge encargos, revisa los servicios y fija la piedra de hogar si vas a usar el poblado como base." },
        { title = "5. Recorre el lado del lago", zone = "Teldrassil", text = "Agrupa las tareas disponibles alrededor del lago Al'Ameth y vuelve por una ruta que complete otros objetivos cercanos. Usa los caminos para orientarte: el relieve del árbol puede alargar un atajo aparente." },
        { title = "6. Reserva una salida al norte", zone = "Teldrassil", text = "Si tu registro te dirige al Claro del Oráculo u otros lugares del norte, reúne todos esos objetivos antes de salir. Da la vuelta si la concentración o el nivel de los enemigos supera lo que puedes manejar." },
        { title = "7. Localiza los servicios de Darnassus", zone = "Teldrassil", text = "Visita Darnassus para entregar, entrenar o reponer suministros cuando te convenga. Localiza también la conexión con Rut'theran y comprueba en el juego qué transportes funcionan en Forever." },
        { title = "8. Comprueba el viaje a Costa Oscura", zone = "Teldrassil", text = "Al rondar el nivel 10, termina las tareas cercanas de dificultad adecuada y consulta el itinerario de la Alianza. Confirma la salida disponible hacia Costa Oscura antes de abandonar tu base." },
    },
})

ns:RegisterGuide({
    id = "horde_durotar_1_10",
    title = "Durotar: de los Retos a Cerrotajo",
    faction = "Horde",
    minLevel = 1,
    maxLevel = 10,
    kind = "Inicio",
    status = "orientativa",
    summary = "Recorrido orientativo de nivel 1-10 basado en Classic, pendiente de verificar en WoW Forever. Usa los asentamientos como referencia y sigue las misiones reales de tu registro.",
    steps = {
        { title = "1. Empieza en el Valle de los Retos", zone = "Durotar", text = "Consulta los encargos disponibles en el valle y en El Cubil. Comprueba los objetivos y aprende las habilidades disponibles antes de emprender una salida larga." },
        { title = "2. Da una vuelta por el valle", zone = "Durotar", text = "Agrupa los objetivos de campo próximos al inicio y regresa con varias entregas. Guarda curación y evita atraer grupos junto a los pasos estrechos." },
        { title = "3. Revisa la salida del inicio", zone = "Durotar", text = "Termina las tareas asequibles que te queden en el valle antes de salir. Entra en cuevas solo con un objetivo activo y recursos para recorrer también el camino de vuelta." },
        { title = "4. Visita Sen'jin", zone = "Durotar", text = "Sigue las indicaciones de tu registro hacia el poblado de Sen'jin si hay encargos disponibles. Reúne las tareas de la costa para resolverlas en una misma excursión." },
        { title = "5. Valora las Islas del Eco", zone = "Durotar", text = "Si las tareas te llevan a las islas, revisa su dificultad antes de cruzar. Busca compañía para campamentos densos u objetivos élite y evita combatir cuando te falte aire o recursos." },
        { title = "6. Establece base en Cerrotajo", zone = "Durotar", text = "Viaja a Cerrotajo y recoge los encargos que encajen con tu nivel. Vende, repón suministros y valora vincular allí la piedra de hogar para las salidas del centro de Durotar." },
        { title = "7. Agrupa el norte y Orgrimmar", zone = "Durotar", text = "Combina los objetivos del norte de Durotar con una visita útil a Orgrimmar. Localiza los instructores que necesites y activa su ruta de vuelo cuando esté disponible." },
        { title = "8. Prepara la entrada a Los Baldíos", zone = "Durotar", text = "Cerca del nivel 10, entrega las tareas terminadas y revisa las indicaciones hacia Los Baldíos. Consulta el itinerario de la Horda y sigue el camino principal cuando estés listo para cambiar de zona." },
    },
})

ns:RegisterGuide({
    id = "horde_mulgore_1_10",
    title = "Mulgore: de la mesa a Cima del Trueno",
    faction = "Horde",
    minLevel = 1,
    maxLevel = 10,
    kind = "Inicio",
    status = "orientativa",
    summary = "Recorrido orientativo de nivel 1-10 basado en Classic, pendiente de verificar en WoW Forever. Ordena las visitas a los poblados y llanuras sin asumir cadenas ni requisitos del servidor.",
    steps = {
        { title = "1. Revisa el Campamento Narache", zone = "Mulgore", text = "Recoge las tareas disponibles en la Mesa de la Nube Roja y lee los objetivos. Identifica dónde vender y entrenar para concentrar los preparativos en cada visita." },
        { title = "2. Rodea el campamento", zone = "Mulgore", text = "Completa los objetivos cercanos en una vuelta por la mesa. Entrega varios juntos y recoge solo los materiales que tus tareas o profesiones necesiten." },
        { title = "3. Comprueba los campamentos hostiles", zone = "Mulgore", text = "Si tu registro te envía a un campamento enemigo, acércate por el borde y observa su dificultad. Evita avanzar hasta el centro sin dejar una ruta de retirada." },
        { title = "4. Baja a Pezuña de Sangre", zone = "Mulgore", text = "Usa el camino de descenso y continúa hasta el Poblado Pezuña de Sangre. Reúne los encargos disponibles y vincula la piedra de hogar si vas a volver al poblado con frecuencia." },
        { title = "5. Haz una salida por el lago", zone = "Mulgore", text = "Agrupa los objetivos disponibles alrededor del lago Toro de Piedra y las llanuras próximas. Revisa el registro antes de regresar para no repetir un viaje por un objeto pendiente." },
        { title = "6. Planifica pozos y colinas", zone = "Mulgore", text = "Cuando tus tareas te lleven a pozos o colinas más alejados, reúne los objetivos de esa dirección. No uses objetos de misión por intuición: su descripción indica el lugar y las condiciones necesarias." },
        { title = "7. Visita Cima del Trueno", zone = "Mulgore", text = "Aprovecha las tareas del norte para acercarte a Cima del Trueno. Localiza ascensores, instructores y la ruta de vuelo, y evita saltar entre plataformas." },
        { title = "8. Decide cuándo ir a Los Baldíos", zone = "Mulgore", text = "Al acercarte al nivel 10, entrega los objetivos terminados y prepara suministros para el viaje hacia el este. Abre el itinerario de la Horda y confirma en el mapa el camino disponible hacia Los Baldíos." },
    },
})

ns:RegisterGuide({
    id = "horde_tirisfal_1_10",
    title = "Tirisfal: de Camposanto a Rémol",
    faction = "Horde",
    minLevel = 1,
    maxLevel = 10,
    kind = "Inicio",
    status = "orientativa",
    summary = "Recorrido orientativo de nivel 1-10 basado en Classic, pendiente de verificar en WoW Forever. No presupone que las misiones o los servicios conserven sus requisitos originales.",
    steps = {
        { title = "1. Revisa Camposanto", zone = "Claros de Tirisfal", text = "Recoge los encargos disponibles en el asentamiento inicial y consulta sus objetivos. Localiza los servicios cercanos antes de salir hacia las zonas de combate." },
        { title = "2. Completa el entorno inmediato", zone = "Claros de Tirisfal", text = "Haz una vuelta corta con los objetivos de campo más cercanos a Camposanto. Regresa a entregar y repón recursos antes de buscar enemigos más alejados." },
        { title = "3. Revisa los interiores pendientes", zone = "Claros de Tirisfal", text = "Si una tarea exige entrar en un edificio o cueva, observa primero el acceso y la dificultad de los enemigos. Lleva comida o curación y evita que una reaparición te deje encerrado." },
        { title = "4. Sigue el camino a Rémol", zone = "Claros de Tirisfal", text = "Cuando termines la etapa inicial, sigue el camino hasta Rémol. Recoge sus tareas y valora fijar la piedra de hogar para usar el poblado como centro de operaciones." },
        { title = "5. Agrupa las granjas", zone = "Claros de Tirisfal", text = "Reúne los encargos disponibles de las granjas y campos del entorno antes de salir. Haz una vuelta por un mismo sector y vuelve a Rémol para entregar sin cruzar toda la zona varias veces." },
        { title = "6. Prepara la salida al lago o al este", zone = "Claros de Tirisfal", text = "Si tu registro señala el lago Aguasclaras o los campamentos del este, completa una dirección antes de empezar la otra. Acércate con cuidado a enemigos a distancia y grupos que puedan luchar juntos." },
        { title = "7. Localiza Entrañas", zone = "Claros de Tirisfal", text = "Haz una visita a Entrañas cuando necesites entrenamiento, servicios o entregas allí. Localiza la salida y la ruta de vuelo para que la siguiente visita sea más directa." },
        { title = "8. Valora Bosque de Argénteos", zone = "Claros de Tirisfal", text = "Cerca del nivel 10, termina las tareas asequibles y revisa si tu registro te envía a Bosque de Argénteos. Consulta el itinerario de la Horda y comprueba el camino antes de cambiar de base." },
    },
})

ns:RegisterGuide({
    id = "alliance_zones_10_60",
    title = "Alianza: itinerario por zonas 10-60",
    faction = "Alliance",
    minLevel = 10,
    maxLevel = 60,
    kind = "Ruta por zonas",
    status = "orientativa",
    summary = "Itinerario orientativo basado en zonas de Classic, pendiente de verificar en WoW Forever. Los rangos se solapan: elige una zona por tramo según tareas, viajes y dificultad; no es una ruta de speedrun ni misión por misión.",
    steps = {
        { title = "1. Nivel 10-15: elige una base cercana", zone = "Páramos de Poniente / Loch Modan / Costa Oscura", text = "Desde Elwynn valora Páramos de Poniente, desde Dun Morogh Loch Modan y desde Teldrassil Costa Oscura. Elige la alternativa accesible que tenga tareas adecuadas y organiza las salidas desde su poblado principal." },
        { title = "2. Nivel 15-20: termina un sector", zone = "Páramos de Poniente / Loch Modan / Costa Oscura", text = "Continúa en la zona elegida mientras conserve tareas de dificultad razonable y viajes cortos. Si solo quedan objetivos de grupo o muy superiores a tu nivel, usa otra de estas zonas para completar el tramo." },
        { title = "3. Nivel 20-24: abre el siguiente centro", zone = "Montañas Crestagrana / Los Humedales / Vallefresno", text = "Escoge un centro con misiones de tu facción: las tres zonas son alternativas, no paradas obligatorias. Activa la ruta de vuelo disponible y reúne los encargos cercanos antes de internarte en el campo." },
        { title = "4. Nivel 24-28: encadena salidas cortas", zone = "Bosque del Ocaso / Los Humedales / Vallefresno", text = "Valora Bosque del Ocaso si estás en los Reinos del Este, o continúa en Vallefresno si juegas en Kalimdor. Agrupa objetivos por dirección y deja los enemigos élite para un grupo o un regreso posterior." },
        { title = "5. Nivel 28-32: agota lo asequible", zone = "Bosque del Ocaso / Laderas de Trabalomas / Mil Agujas", text = "Termina las tareas útiles de tu zona y comprueba qué alternativas ofrecen realmente encargos para la Alianza. Considera Mil Agujas solo si el desplazamiento te compensa y tienes tareas adecuadas allí." },
        { title = "6. Nivel 32-36: elige un continente", zone = "Vega de Tuercespina / Desolace", text = "Usa Vega de Tuercespina en los Reinos del Este o Desolace en Kalimdor si sus tareas encajan con tu nivel. Establece una base y combina objetivos próximos antes de viajar a otra zona." },
        { title = "7. Nivel 36-40: completa los bordes", zone = "Tierras Altas de Arathi / Vega de Tuercespina / Desolace", text = "Alterna una zona de este tramo con tareas pendientes asequibles de la anterior si faltan opciones. Revisa con especial cuidado los objetivos de fortalezas y campamentos grandes antes de entrar solo." },
        { title = "8. Nivel 40-44: abre rutas de viaje", zone = "Tierras Inhóspitas / Feralas / Marjal Revolcafango", text = "Elige la zona que ofrezca encargos apropiados y transporte accesible para tu personaje. Activa sus conexiones de vuelo al llegar y comprueba en el cliente las condiciones y el precio de la montura." },
        { title = "9. Nivel 44-48: concentra las entregas", zone = "Tanaris / Tierras del Interior", text = "Valora Tanaris o Tierras del Interior según los encargos que encuentres y tus conexiones de viaje. Reúne las tareas de un mismo sector y evita cruzar el mapa para entregar un único objetivo." },
        { title = "10. Nivel 48-52: comprueba la dificultad", zone = "La Garganta de Fuego / Cráter de Un'Goro", text = "Entra en estas zonas cuando los primeros enemigos y tareas resulten manejables para tu equipo. En Un'Goro observa las patrullas grandes; en La Garganta de Fuego presta atención al relieve y a las salidas." },
        { title = "11. Nivel 52-56: prepara el tramo final", zone = "Frondavil / Tierras de la Peste del Oeste", text = "Escoge los encargos de dificultad adecuada y combina varias entregas por salida. Conserva consumibles y deja para grupo los objetivos que el registro o la dificultad real indiquen como peligrosos." },
        { title = "12. Nivel 56-60: completa lo disponible", zone = "Cuna del Invierno / Tierras de la Peste del Este / Silithus", text = "Revisa los centros de estas zonas y termina también tareas pendientes que sigan dando experiencia útil. El contenido de Silithus y los requisitos finales dependen de Forever: confirma su disponibilidad antes de viajar." },
    },
})

ns:RegisterGuide({
    id = "horde_zones_10_60",
    title = "Horda: itinerario por zonas 10-60",
    faction = "Horde",
    minLevel = 10,
    maxLevel = 60,
    kind = "Ruta por zonas",
    status = "orientativa",
    summary = "Itinerario orientativo basado en zonas de Classic, pendiente de verificar en WoW Forever. Los niveles son aproximados y las zonas son alternativas; no es una ruta de speedrun ni una guía completa misión por misión.",
    steps = {
        { title = "1. Nivel 10-15: elige la salida cercana", zone = "Los Baldíos / Bosque de Argénteos", text = "Desde Durotar o Mulgore valora Los Baldíos, y desde Tirisfal Bosque de Argénteos. Reúne las tareas del primer centro accesible y activa la conexión de vuelo que encuentres disponible." },
        { title = "2. Nivel 15-20: trabaja desde una base", zone = "Los Baldíos / Bosque de Argénteos", text = "En Los Baldíos agrupa tus salidas desde El Cruce u otro centro con encargos adecuados; en Argénteos revisa los alrededores de El Sepulcro. No cambies de continente mientras tengas tareas asequibles cerca, salvo que quieras hacerlo por variedad." },
        { title = "3. Nivel 20-24: combina zonas vecinas", zone = "Sierra Espolón / Vallefresno / Los Baldíos", text = "Valora Sierra Espolón o Vallefresno si ya estás en Kalimdor y sus centros ofrecen tareas de tu nivel. Completa objetivos cercanos pendientes de Los Baldíos antes de trasladar tu base." },
        { title = "4. Nivel 24-28: decide dónde continuar", zone = "Laderas de Trabalomas / Mil Agujas", text = "Desde Argénteos suele resultar práctico revisar Trabalomas, mientras que Mil Agujas es una alternativa desde Los Baldíos. Comprueba los niveles al llegar y no asumas que todos los encargos de la zona pueden hacerse solos." },
        { title = "5. Nivel 28-32: organiza una vuelta larga", zone = "Mil Agujas / Laderas de Trabalomas / Desolace", text = "Termina los sectores adecuados de Mil Agujas o Trabalomas antes de buscar otra base. Si eliges Desolace, consulta el acceso en el mapa y reúne sus encargos antes de alejarte del asentamiento." },
        { title = "6. Nivel 32-36: reduce los grandes viajes", zone = "Vega de Tuercespina / Desolace", text = "Escoge Vega de Tuercespina o Desolace según tu continente y la oferta de tareas de la Horda. Mantén una base para entregar y evita alternar ambos continentes por encargos aislados." },
        { title = "7. Nivel 36-40: revisa los campamentos", zone = "Tierras Altas de Arathi / Vega de Tuercespina / Desolace", text = "Continúa con tareas apropiadas de tu zona o abre una alternativa si solo quedan objetivos demasiado difíciles. Observa patrullas y enemigos élite antes de entrar en ruinas, fortalezas o campamentos densos." },
        { title = "8. Nivel 40-44: conecta nuevos centros", zone = "Feralas / Marjal Revolcafango / Tierras Inhóspitas", text = "Elige una zona con encargos apropiados de la Horda y activa su conexión de vuelo al llegar. Agrupa el viaje con entrenamiento y comprueba en el cliente las condiciones y el precio de la montura." },
        { title = "9. Nivel 44-48: agrupa por dirección", zone = "Tanaris / Tierras del Interior", text = "Valora Tanaris o Tierras del Interior en función de las tareas y rutas de vuelo que tengas abiertas. Reúne los encargos de cada sector y lleva suministros para completar varios antes de regresar." },
        { title = "10. Nivel 48-52: entra con recursos", zone = "Cráter de Un'Goro / La Garganta de Fuego", text = "Comprueba la dificultad de los primeros objetivos y conserva una salida si encuentras grupos demasiado fuertes. Vigila las patrullas grandes de Un'Goro y los desniveles de La Garganta de Fuego." },
        { title = "11. Nivel 52-56: combina tareas asequibles", zone = "Frondavil / Tierras de la Peste del Oeste", text = "Revisa los centros disponibles y empieza por objetivos que puedas completar con tu equipo actual. Alterna con tareas útiles pendientes si solo encuentras grupos densos, enemigos élite o requisitos que aún no cumples." },
        { title = "12. Nivel 56-60: cierra el recorrido", zone = "Cuna del Invierno / Tierras de la Peste del Este / Silithus", text = "Elige los encargos disponibles que se adapten a tu nivel y completa entregas pendientes que sigan siendo útiles. Confirma en Forever el contenido y los requisitos de Silithus y de las tareas finales antes de desplazarte." },
    },
})
