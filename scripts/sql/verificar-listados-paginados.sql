-- Test runner creates pg_temp copies of the RPCs targeting these temp tables.
-- Everything runs in a transaction which is always rolled back.
CREATE TEMP TABLE st_test_proveedores (LIKE public.proveedores);
CREATE TEMP TABLE st_test_ordenes (LIKE public.ordenes_compra);
ALTER TABLE pg_temp.st_test_proveedores ENABLE ROW LEVEL SECURITY;
ALTER TABLE pg_temp.st_test_ordenes ENABLE ROW LEVEL SECURITY;
CREATE POLICY lectura_test ON pg_temp.st_test_proveedores FOR SELECT TO authenticated USING (true);
CREATE POLICY lectura_test ON pg_temp.st_test_ordenes FOR SELECT TO authenticated USING (true);
GRANT SELECT ON pg_temp.st_test_proveedores, pg_temp.st_test_ordenes TO authenticated;

INSERT INTO pg_temp.st_test_proveedores (id,codigo,nombre,contacto,telefono,email,categorias,dias_credito)
SELECT i,lpad(i::text,6,'0'),'Proveedor '||lpad(i::text,4,'0'),'Atención '||i,
    '0414-'||i,'contacto'||i||'@example.com','["Lácteos","Víveres"]',30 FROM generate_series(1,1025) i;
UPDATE pg_temp.st_test_proveedores SET nombre='Árbol %_ Straße' WHERE id=1;
UPDATE pg_temp.st_test_proveedores SET nombre=U&'A\0301rbol %_ Stra\00dfe' WHERE id=2;
UPDATE pg_temp.st_test_proveedores SET categorias='"Legado Ácido"' WHERE id=5;
UPDATE pg_temp.st_test_proveedores SET dias_credito=0 WHERE id=2;
UPDATE pg_temp.st_test_proveedores SET dias_credito=NULL WHERE id=3;

INSERT INTO pg_temp.st_test_ordenes(id,usuario_id,numero_orden,proveedor_id,proveedor,tienda_destino,fecha_envio,fecha_recepcion,monto_total)
SELECT i,'00000000-0000-0000-0000-000000000001'::uuid,'OC-'||lpad(i::text,4,'0'),1,'Proveedor','CENTRO',
    date '2026-10-01',NULL,10 FROM generate_series(1,1025) i;
INSERT INTO pg_temp.st_test_ordenes(id,usuario_id,numero_orden,proveedor,tienda_destino,fecha_envio,monto_total)
VALUES(5000,'00000000-0000-0000-0000-000000000002','AJENA','Otra persona','CENTRO','2026-10-01',10);
UPDATE pg_temp.st_test_ordenes SET monto_total=1234.5 WHERE id=999;
UPDATE pg_temp.st_test_ordenes SET fecha_recepcion='2026-10-02' WHERE id=998;

SET LOCAL request.jwt.claim.sub = '00000000-0000-0000-0000-000000000001';
SET LOCAL request.jwt.claims = '{"sub":"00000000-0000-0000-0000-000000000001","role":"authenticated"}';
SET LOCAL ROLE authenticated;
DO $test$
DECLARE r record;
BEGIN
    SELECT * INTO r FROM pg_temp.st_listar_ordenes('{}','',1);
    IF r.total<>1025 OR jsonb_array_length(r.registros)<>20 OR (r.registros->0->>'id')::int<>1025 THEN
        RAISE EXCEPTION 'Primera pagina de ordenes incorrecta'; END IF;
    IF (r.registros->0) ? 'pagada' OR (r.registros->0) ? 'detalles_productos' THEN
        RAISE EXCEPTION 'El listado contiene campos o detalles adicionales'; END IF;
    SELECT * INTO r FROM pg_temp.st_listar_ordenes('{}','',52);
    IF r.pagina<>52 OR jsonb_array_length(r.registros)<>5 THEN RAISE EXCEPTION 'Ultima pagina de ordenes incorrecta'; END IF;
    SELECT * INTO r FROM pg_temp.st_listar_ordenes(ARRAY['1.234,50','centro','enviada'],'',1);
    IF r.total<>1 OR (r.registros->0->>'id')::int<>999 THEN RAISE EXCEPTION 'Filtro de monto incorrecto'; END IF;
    SELECT * INTO r FROM pg_temp.st_listar_ordenes(ARRAY['01/11/2026','recibido'],'2026-10-02',1);
    IF r.total<>1 OR (r.registros->0->>'id')::int<>998 THEN RAISE EXCEPTION 'Filtro de vencimiento/recepcion incorrecto'; END IF;
    SELECT * INTO r FROM pg_temp.st_listar_ordenes(ARRAY['AJENA'],'',1);
    IF r.total<>0 THEN RAISE EXCEPTION 'Una orden ajena es visible'; END IF;
    SELECT * INTO r FROM pg_temp.st_listar_proveedores('{}','nombre',false,52,NULL);
    IF r.total<>1025 OR jsonb_array_length(r.registros)<>5 THEN RAISE EXCEPTION 'Paginacion de proveedores incorrecta'; END IF;
    SELECT * INTO r FROM pg_temp.st_listar_proveedores(ARRAY['arbol','strasse','%_'],'nombre',false,1,NULL);
    IF r.total<>2 OR (r.registros->0->>'id')::int<>1 THEN RAISE EXCEPTION 'Acentos/casefold/literales incorrectos'; END IF;
    SELECT * INTO r FROM pg_temp.st_listar_proveedores(ARRAY['arbol'],'nombre',true,1,NULL);
    IF r.total<>2 OR (r.registros->0->>'id')::int<>2 THEN RAISE EXCEPTION 'Desempate descendente incorrecto'; END IF;
    SELECT * INTO r FROM pg_temp.st_listar_proveedores(ARRAY['lacteos','atencion','001025'],'nombre',false,1,1);
    IF r.total<>1 OR (r.registros->0->>'id')::int<>1025 OR (r.seleccion->>'id')::int<>1 THEN
        RAISE EXCEPTION 'Categorias/contacto/ficha fuera de pagina incorrectos'; END IF;
    SELECT * INTO r FROM pg_temp.st_listar_proveedores(ARRAY['acido'],'nombre',false,1,NULL);
    IF r.total<>1 OR (r.registros->0->>'id')::int<>5 THEN RAISE EXCEPTION 'Categoria antigua incorrecta'; END IF;
END $test$;

SET LOCAL ROLE anon;
DO $test$ BEGIN
    IF has_function_privilege(current_user,'public.st_listar_ordenes(text[],text,integer)','EXECUTE')
       OR has_function_privilege(current_user,'public.st_listar_proveedores(text[],text,boolean,integer,integer)','EXECUTE') THEN
        RAISE EXCEPTION 'Se concedio ejecucion anonima';
    END IF;
END $test$;

SET LOCAL ROLE authenticated;
SET LOCAL request.jwt.claim.sub = '00000000-0000-0000-0000-000000000002';
DO $test$ DECLARE r record;
BEGIN
    SELECT * INTO r FROM pg_temp.st_listar_ordenes('{}','',1);
    IF r.total<>1 OR (r.registros->0->>'id')::int<>5000 THEN RAISE EXCEPTION 'Aislamiento entre usuarios incorrecto'; END IF;
END $test$;

SET LOCAL request.jwt.claim.sub = '';
SET LOCAL request.jwt.claims = '{}';
DO $test$ BEGIN
    BEGIN
        PERFORM * FROM pg_temp.st_listar_ordenes('{}','',1);
        RAISE EXCEPTION 'Se permitio listar sin identidad';
    EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $test$;
