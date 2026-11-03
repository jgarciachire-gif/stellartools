WITH datos(sede,codigo,fecha_venta,descargos) AS (VALUES
('CENTRO'::text,'X'::text,date '2026-10-14',6::numeric),
('CENTRO','OTRO',date '2026-10-15',3),
('CENTRO','X',date '2026-10-20',0),
('CENTRO','OTRO',date '2026-10-21',-4),
('CENTRO','X',date '2026-10-31',12),
('CENTRO','OTRO',date '2026-11-01',1),
('SAN DIEGO','X',date '2026-10-14',2),
('SAN DIEGO','OTRO',date '2026-10-15',4),
('Centro ','X',date '2026-10-14',1),
(NULL,'X',date '2026-10-14',1)
), anterior AS (WITH calendario AS (
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
        FROM generate_series(date '2026-10-01'::timestamp, date '2026-11-03'::timestamp, interval '1 day') AS gs(d)
    ),
    dias_cubiertos AS (
        SELECT DISTINCT vk.sede AS sede_dato, vk.fecha_venta AS fecha
        FROM (SELECT * FROM datos WHERE descargos > 0) vk
        WHERE vk.fecha_venta BETWEEN date '2026-10-01' AND date '2026-11-03'
    ),
    ventas_dia AS (
        SELECT
            vk.sede AS sede_dato,
            vk.codigo AS codigo_dato,
            vk.fecha_venta AS fecha,
            SUM(vk.descargos) AS unidades
        FROM (SELECT * FROM datos WHERE descargos > 0) vk
        WHERE vk.fecha_venta BETWEEN date '2026-10-01' AND date '2026-11-03'
          AND vk.descargos > 0
          AND vk.codigo = ANY(array['X','X','SIN-VENTAS']::text[])
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
    ORDER BY r.sede_dato, r.codigo_dato), nuevo AS (WITH calendario AS (
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
        FROM generate_series(date '2026-10-01'::timestamp, date '2026-11-03'::timestamp, interval '1 day') AS gs(d)
    ),
    ventas_dia AS (
        SELECT
            vk.sede AS sede_dato,
            vk.codigo AS codigo_dato,
            vk.fecha_venta AS fecha,
            SUM(vk.descargos) AS unidades
        FROM (SELECT * FROM datos WHERE descargos > 0) vk
        WHERE vk.fecha_venta BETWEEN date '2026-10-01' AND date '2026-11-03'
          AND vk.descargos > 0
          AND vk.codigo = ANY(array['X','X','SIN-VENTAS']::text[])
        GROUP BY vk.sede, vk.codigo, vk.fecha_venta
    ),
    pares AS (
        SELECT DISTINCT vd.sede_dato, vd.codigo_dato
        FROM ventas_dia vd
    ),
    dias_cubiertos AS MATERIALIZED (
        -- Coverage includes sales of ANY product, for the relevant stores/days.
        -- OFFSET 0 keeps the indexed existence probe instead of a full-range join.
        SELECT sedes.sede_dato, c.fecha
        FROM (SELECT DISTINCT p.sede_dato FROM pares p) sedes
        CROSS JOIN calendario c
        WHERE EXISTS (
            SELECT 1 FROM datos vk
            WHERE vk.sede = sedes.sede_dato
              AND vk.fecha_venta = c.fecha
              AND vk.descargos > 0
            OFFSET 0
        )
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
    ORDER BY r.sede_dato, r.codigo_dato), diferencias AS ((select * from anterior except all select * from nuevo) union all (select * from nuevo except all select * from anterior)) select (select count(*) from diferencias) as diferencias, (select count(*) from nuevo) as pares_resultantes, (select dias_cubiertos from nuevo where sede_dato='CENTRO') as dias_centro;
