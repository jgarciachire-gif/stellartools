-- Deploy the previous backend routes before reverting these new RPCs.
-- No table, record, policy, or existing function is removed.
BEGIN;
SET LOCAL lock_timeout = '2s';
DROP FUNCTION IF EXISTS public.st_listar_ordenes(text[],text,integer);
DROP FUNCTION IF EXISTS public.st_listar_proveedores(text[],text,boolean,integer,integer);
DROP FUNCTION IF EXISTS public.st_monto_busqueda(numeric);
DROP FUNCTION IF EXISTS public.st_normalizar_listado(text);
COMMIT;
