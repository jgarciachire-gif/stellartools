-- Replace only an existing function, preserving its ownership and grants.
BEGIN;
SET LOCAL lock_timeout = '2s';
DO $guard$
BEGIN
    IF to_regprocedure('public.obtener_demanda_comercial_kardex(date,date,text[])') IS NULL THEN
        RAISE EXCEPTION 'La funcion original no existe; no se crea una funcion publica nueva.';
    END IF;
END $guard$;

CREATE OR REPLACE FUNCTION public.obtener_demanda_comercial_kardex(p_fecha_inicio date, p_fecha_fin date, p_codigos text[])
 RETURNS TABLE(sede text, codigo text, unidades_mes numeric, dias_cubiertos bigint, demanda_regular numeric, demanda_alta numeric, semanas_regulares bigint, semanas_alta bigint)
 LANGUAGE plpgsql
 STABLE
 SET search_path TO ''
AS $function$
BEGIN
    IF p_fecha_inicio IS NULL OR p_fecha_fin IS NULL OR p_fecha_inicio > p_fecha_fin THEN
        RAISE EXCEPTION 'Rango de fechas inválido';
    END IF;

    IF p_codigos IS NULL OR cardinality(p_codigos) = 0 THEN
        RETURN;
    END IF;

    RETURN QUERY
    WITH calendario AS (
        SELECT
            gs.d::date AS fecha,
            date_trunc('week', gs.d)::date AS semana_inicio,
            (
                date_trunc('week', make_date(EXTRACT(YEAR FROM gs.d)::int, EXTRACT(MONTH FROM gs.d)::int, 15))::date
                = date_trunc('week', gs.d)::date
                OR
                date_trunc('week', (date_trunc('month', gs.d) + interval '1 month - 1 day'))::date
                = date_trunc('week', gs.d)::date
            ) AS es_semana_alta
        FROM generate_series(p_fecha_inicio::timestamp, p_fecha_fin::timestamp, interval '1 day') AS gs(d)
    ),
    dias_cubiertos AS (
        SELECT DISTINCT vk.sede AS sede_dato, vk.fecha_venta AS fecha
        FROM (SELECT * FROM public.ventas_kardex WHERE descargos > 0) vk
        WHERE vk.fecha_venta BETWEEN p_fecha_inicio AND p_fecha_fin
    ),
    ventas_dia AS (
        SELECT
            vk.sede AS sede_dato,
            vk.codigo AS codigo_dato,
            vk.fecha_venta AS fecha,
            SUM(vk.descargos) AS unidades
        FROM (SELECT * FROM public.ventas_kardex WHERE descargos > 0) vk
        WHERE vk.fecha_venta BETWEEN p_fecha_inicio AND p_fecha_fin
          AND vk.descargos > 0
          AND vk.codigo = ANY(p_codigos)
        GROUP BY vk.sede, vk.codigo, vk.fecha_venta
    ),
    pares AS (
        SELECT DISTINCT vd.sede_dato, vd.codigo_dato
        FROM ventas_dia vd
    ),
    base AS (
        SELECT
            p.sede_dato,
            p.codigo_dato,
            c.fecha,
            c.semana_inicio,
            c.es_semana_alta,
            COALESCE(v.unidades, 0::numeric) AS unidades
        FROM pares p
        JOIN calendario c ON TRUE
        JOIN dias_cubiertos dc
          ON dc.sede_dato = p.sede_dato
         AND dc.fecha = c.fecha
        LEFT JOIN ventas_dia v
          ON v.sede_dato = p.sede_dato
         AND v.codigo_dato = p.codigo_dato
         AND v.fecha = c.fecha
    ),
    resumen AS (
        SELECT
            b.sede_dato,
            b.codigo_dato,
            SUM(b.unidades) AS unidades_mes,
            COUNT(*) AS dias_cubiertos,
            SUM(b.unidades) FILTER (WHERE NOT b.es_semana_alta)
                / NULLIF(COUNT(*) FILTER (WHERE NOT b.es_semana_alta), 0) AS demanda_regular,
            SUM(b.unidades) FILTER (WHERE b.es_semana_alta)
                / NULLIF(COUNT(*) FILTER (WHERE b.es_semana_alta), 0) AS demanda_alta,
            COUNT(DISTINCT b.semana_inicio) FILTER (WHERE NOT b.es_semana_alta) AS semanas_regulares,
            COUNT(DISTINCT b.semana_inicio) FILTER (WHERE b.es_semana_alta) AS semanas_alta
        FROM base b
        GROUP BY b.sede_dato, b.codigo_dato
    )
    SELECT
        r.sede_dato,
        r.codigo_dato,
        r.unidades_mes,
        r.dias_cubiertos,
        COALESCE(r.demanda_regular, 0::numeric),
        COALESCE(r.demanda_alta, 0::numeric),
        COALESCE(r.semanas_regulares, 0::bigint),
        COALESCE(r.semanas_alta, 0::bigint)
    FROM resumen r
    ORDER BY r.sede_dato, r.codigo_dato;
END;
$function$;
COMMIT;
