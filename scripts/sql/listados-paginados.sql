-- Read-only pagination, invoked with the user's JWT. RLS remains in effect.
-- Install listados-normalizacion.sql first. Deployment runner wraps all DDL in
-- one transaction and revokes default PUBLIC execution before committing.

CREATE OR REPLACE FUNCTION public.st_monto_busqueda(p_monto numeric)
RETURNS text LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE SECURITY INVOKER
SET search_path = '' AS $fn$
DECLARE
    bits bytea; signo boolean; exponente integer; mantisa numeric;
    numerador numeric; denominador numeric; centavos numeric; resto numeric; i integer;
BEGIN
    -- Match Python's binary-float formatting, including half-even ties and -0.00.
    bits := float8send(coalesce(p_monto, 0)::double precision);
    signo := get_byte(bits, 0) >= 128;
    exponente := (get_byte(bits, 0) % 128) * 16 + get_byte(bits, 1) / 16;
    mantisa := get_byte(bits, 1) % 16;
    FOR i IN 2..7 LOOP mantisa := mantisa * 256 + get_byte(bits, i); END LOOP;
    IF exponente = 2047 THEN
        RETURN CASE WHEN mantisa <> 0 THEN 'nan' WHEN signo THEN '-inf' ELSE 'inf' END;
    END IF;
    IF exponente > 0 THEN mantisa := mantisa + 4503599627370496; END IF;
    exponente := greatest(exponente, 1) - 1075;
    numerador := mantisa * 100 * power(2::numeric, greatest(exponente, 0));
    denominador := power(2::numeric, greatest(-exponente, 0));
    centavos := div(numerador, denominador);
    resto := mod(numerador, denominador);
    IF resto * 2 > denominador OR (resto * 2 = denominador AND mod(centavos, 2) = 1) THEN
        centavos := centavos + 1;
    END IF;
    RETURN CASE WHEN signo THEN '-' ELSE '' END || translate(
        to_char(centavos / 100, 'FM' || repeat('999,', length(trunc(centavos / 100)::text) / 3) || '990.00'), ',.', '.,');
EXCEPTION WHEN numeric_value_out_of_range THEN
    RETURN CASE WHEN p_monto < 0 THEN '-inf' ELSE 'inf' END;
END $fn$;

CREATE OR REPLACE FUNCTION public.st_listar_ordenes(
    p_criterios text[] DEFAULT '{}', p_fecha text DEFAULT '', p_pagina integer DEFAULT 1
)
RETURNS TABLE(registros jsonb, total bigint, pagina integer)
LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path = '' AS $fn$
BEGIN
    IF auth.uid() IS NULL THEN RAISE EXCEPTION 'Autenticacion requerida' USING ERRCODE = '42501'; END IF;
    RETURN QUERY
    WITH criterios AS MATERIALIZED (
        SELECT lower(coalesce(t, '')) AS valor FROM unnest(coalesce(p_criterios, '{}')) t
        WHERE coalesce(t, '') <> ''
    ), cabeceras AS NOT MATERIALIZED (
        SELECT o.id, o.numero_orden, o.proveedor, o.tienda_destino, o.fecha_envio,
               o.fecha_recepcion, o.monto_total, o.estatus, o.proveedor_id,
               CASE WHEN pr.id IS NULL THEN NULL ELSE jsonb_build_object(
                   'nombre', pr.nombre, 'dias_credito', pr.dias_credito) END AS proveedores,
               CASE WHEN EXISTS (SELECT 1 FROM criterios) THEN lower(concat_ws(' ', coalesce(o.numero_orden, ''),
                   coalesce(nullif(pr.nombre, ''), o.proveedor, ''), coalesce(o.tienda_destino, ''),
                   CASE WHEN o.fecha_recepcion IS NOT NULL AND coalesce(pr.dias_credito, CASE WHEN pr.id IS NULL THEN 30 END) <> 0
                        THEN to_char(o.fecha_recepcion + coalesce(pr.dias_credito, 30), 'DD/MM/YYYY') ELSE '' END,
                   '$' || public.st_monto_busqueda(o.monto_total),
                   CASE WHEN o.fecha_recepcion IS NULL THEN 'Enviada' ELSE 'Despacho Recibido' END)) ELSE '' END AS busqueda
        FROM public.ordenes_compra o LEFT JOIN public.proveedores pr ON pr.id = o.proveedor_id
        WHERE o.usuario_id = (SELECT auth.uid())
          AND (coalesce(p_fecha, '') = '' OR o.fecha_envio::text = p_fecha OR o.fecha_recepcion::text = p_fecha)
    ), filtradas AS MATERIALIZED (
        SELECT c.* FROM cabeceras c WHERE NOT EXISTS (
            SELECT 1 FROM criterios t WHERE strpos(c.busqueda, t.valor) = 0
        )
    ), conteo AS (
        SELECT count(*) AS cantidad FROM filtradas
    ), meta AS (
        SELECT c.cantidad, least(greatest(coalesce(p_pagina, 1), 1), greatest(1, (c.cantidad + 19) / 20)::integer) AS numero
        FROM conteo c
    ), elegidas AS (
        SELECT f.*, row_number() OVER (ORDER BY f.fecha_envio DESC, f.id DESC) AS posicion
        FROM filtradas f ORDER BY f.fecha_envio DESC, f.id DESC
        LIMIT 20 OFFSET ((SELECT m.numero FROM meta m)::bigint - 1) * 20
    )
    SELECT coalesce((SELECT jsonb_agg(to_jsonb(e) - 'busqueda' - 'posicion' ORDER BY e.posicion) FROM elegidas e), '[]'),
           m.cantidad, m.numero FROM meta m;
END $fn$;

CREATE OR REPLACE FUNCTION public.st_listar_proveedores(
    p_terminos text[] DEFAULT '{}', p_orden text DEFAULT 'nombre', p_desc boolean DEFAULT false,
    p_pagina integer DEFAULT 1, p_seleccion integer DEFAULT NULL
)
RETURNS TABLE(registros jsonb, total bigint, pagina integer, etiquetas jsonb, seleccion jsonb)
LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path = '' AS $fn$
DECLARE v_orden text;
BEGIN
    IF auth.uid() IS NULL THEN RAISE EXCEPTION 'Autenticacion requerida' USING ERRCODE = '42501'; END IF;
    v_orden := CASE WHEN p_orden IN ('codigo', 'nombre', 'contacto', 'telefono', 'email') THEN p_orden ELSE 'nombre' END;
    RETURN QUERY
    WITH criterios AS MATERIALIZED (
        SELECT public.st_normalizar_listado(t) AS valor FROM unnest(coalesce(p_terminos, '{}')) t
    ), directorio AS MATERIALIZED (
        SELECT p AS proveedor, public.st_normalizar_listado(coalesce(to_jsonb(p)->>v_orden, '')) COLLATE "C" AS clave,
            CASE WHEN cardinality(coalesce(p_terminos, '{}')) > 0 THEN public.st_normalizar_listado(
                concat_ws(' ', coalesce(p.codigo, ''), coalesce(p.nombre, ''), coalesce(p.contacto, ''),
                    coalesce(p.telefono, ''), coalesce(p.email, '')) || ' ' ||
                CASE WHEN jsonb_typeof(p.categorias) = 'array' THEN coalesce((
                    SELECT string_agg(coalesce(x.valor, 'None'), ' ' ORDER BY x.posicion)
                    FROM jsonb_array_elements_text(p.categorias) WITH ORDINALITY AS x(valor, posicion)
                ), '') ELSE coalesce(p.categorias #>> '{}', '') END
            ) ELSE '' END AS busqueda
        FROM public.proveedores p
    ), filtrados AS MATERIALIZED (
        SELECT d.* FROM directorio d WHERE NOT EXISTS (
            SELECT 1 FROM criterios t WHERE strpos(d.busqueda, t.valor) = 0
        )
    ), conteo AS (
        SELECT count(*) AS cantidad FROM filtrados
    ), meta AS (
        SELECT c.cantidad, least(greatest(coalesce(p_pagina, 1), 1), greatest(1, (c.cantidad + 19) / 20)::integer) AS numero
        FROM conteo c
    ), elegidos AS (
        SELECT f.proveedor, row_number() OVER (ORDER BY
            CASE WHEN coalesce(p_desc, false) THEN f.clave END COLLATE "C" DESC,
            CASE WHEN NOT coalesce(p_desc, false) THEN f.clave END COLLATE "C" ASC,
            CASE WHEN coalesce(p_desc, false) THEN (f.proveedor).id END DESC,
            CASE WHEN NOT coalesce(p_desc, false) THEN (f.proveedor).id END ASC) AS posicion
        FROM filtrados f ORDER BY
            CASE WHEN coalesce(p_desc, false) THEN f.clave END COLLATE "C" DESC,
            CASE WHEN NOT coalesce(p_desc, false) THEN f.clave END COLLATE "C" ASC,
            CASE WHEN coalesce(p_desc, false) THEN (f.proveedor).id END DESC,
            CASE WHEN NOT coalesce(p_desc, false) THEN (f.proveedor).id END ASC
        LIMIT 20 OFFSET ((SELECT m.numero FROM meta m)::bigint - 1) * 20
    ), categorias AS (
        SELECT DISTINCT x.valor COLLATE "C" AS valor FROM public.proveedores p
        CROSS JOIN LATERAL jsonb_array_elements_text(
            CASE WHEN jsonb_typeof(p.categorias) = 'array' THEN p.categorias ELSE '[]' END) x(valor)
    )
    SELECT coalesce((SELECT jsonb_agg(to_jsonb(e.proveedor) ORDER BY e.posicion) FROM elegidos e), '[]'),
        m.cantidad, m.numero,
        coalesce((SELECT jsonb_agg(c.valor ORDER BY c.valor COLLATE "C") FROM categorias c), '[]'),
        (SELECT to_jsonb(p) FROM public.proveedores p WHERE p.id = p_seleccion)
    FROM meta m;
END $fn$;

REVOKE ALL ON FUNCTION public.st_normalizar_listado(text), public.st_monto_busqueda(numeric),
    public.st_listar_ordenes(text[],text,integer), public.st_listar_proveedores(text[],text,boolean,integer,integer)
    FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.st_normalizar_listado(text), public.st_monto_busqueda(numeric),
    public.st_listar_ordenes(text[],text,integer), public.st_listar_proveedores(text[],text,boolean,integer,integer)
    TO authenticated;

NOTIFY pgrst, 'reload schema';
