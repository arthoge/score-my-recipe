# Guía visual y técnica: Make it better

Esta guía explica cómo ejecutar y comprobar visualmente la funcionalidad **Make it better**. También documenta cómo está conectada la interfaz con la API.

## Requisitos

- Python 3.12 o superior y [`uv`](https://docs.astral.sh/uv/)
- Node.js 20–24 y `pnpm`
- Dos terminales, una para la API y otra para el frontend

## Arranque local

Desde la raíz del repositorio, prepara las dependencias si aún no lo has hecho:

```bash
cd server
uv sync --all-extras
```

En una primera terminal, inicia la API:

```bash
cd server
uv run uvicorn api.api:app --reload
```

La API quedará disponible en <http://localhost:8000> y su documentación interactiva en <http://localhost:8000/docs>.

En otra terminal, prepara e inicia el frontend:

```bash
cd frontend
cp .env.example .env
pnpm install --frozen-lockfile
pnpm dev
```

Abre <http://localhost:5173/add>. El archivo `frontend/.env` debe contener `PUBLIC_RECIPE_API_URL=http://localhost:8000`, que es el valor incluido en `.env.example`.

## Prueba visual: no aplicar cambios

El catálogo de demostración contiene una recomendación para **Chocolate yogurt**. Para probarla:

1. Abre la página **Add a recipe**.
2. Escribe `Chocolate yogurt` en el campo de receta.
3. Pulsa **Make it better**, situado junto a los botones de ejemplo bajo “Or try an example recipe”.
4. Comprueba que el primer diálogo muestra dos columnas:
   - **Original Recipe**: `Chocolate yogurt`, con Nutri-Score D y Green-Score D.
   - **Improved Recipe**: `Organic plain yogurt`, con Nutri-Score A y Green-Score A.
5. Pulsa **No**.

Resultado esperado: el diálogo se cierra inmediatamente y el texto de la receta continúa siendo `Chocolate yogurt`.

## Prueba visual: aplicar sólo una selección

Para comprobar la selección individual, introduce estas dos líneas:

```text
Chocolate yogurt
Plain yogurt
```

Después:

1. Pulsa **Make it better** y después **Switch**.
2. El segundo diálogo muestra una casilla por recomendación disponible. Ninguna está seleccionada inicialmente.
3. Marca solamente `Chocolate yogurt → Organic plain yogurt`.
4. Pulsa **Apply selected changes**.

Resultado esperado:

```text
Organic plain yogurt
Plain yogurt
```

La segunda línea no debe cambiar. Repite la prueba marcando más de una casilla para confirmar que se reemplazan exclusivamente las opciones marcadas.

## Comprobación directa de la API

La API puede verificarse sin la interfaz:

```bash
curl -X POST http://localhost:8000/v1/make-it-better/check \
  -H 'Content-Type: application/json' \
  -d '{"ingredients":["Chocolate yogurt","Tomato"]}'
```

La respuesta incluye una sugerencia para `Chocolate yogurt` y mantiene `Tomato` dentro de `noImprovement`. La API no aplica cambios: sólo devuelve sugerencias.

## Implementación

El flujo se divide deliberadamente entre presentación y lógica de negocio:

```text
Add Recipe
  → parse_text
  → POST /v1/make-it-better/check
  → diálogo de comparación
  → Switch
  → diálogo de selección
  → Apply selected changes
  → actualización local de sólo los productos marcados
```

### Backend

- `server/api/make_it_better_catalog.json` es el catálogo local de productos y alternativas permitidas.
- `server/api/improvements.py` normaliza nombres, compara Nutri-Score y Green-Score, y elige una única alternativa: la de mayor mejora combinada.
- `server/api/api.py` expone `POST /v1/make-it-better/check`.
- La respuesta usa `suggestions` para las alternativas posibles y `noImprovement` para productos sin una mejora declarada.

El endpoint es informativo y no modifica recetas ni datos de productos. De este modo, la decisión final permanece en la interfaz y requiere una selección explícita.

### Frontend

- `frontend/src/routes/add/+page.svelte` llama a la API cuando se pulsa **Make it better** y actualiza el texto sólo al recibir selecciones confirmadas.
- `frontend/src/lib/ui/MakeItBetterDialog.svelte` contiene los dos pasos del diálogo. Usa el diálogo nativo y las clases DaisyUI existentes para conservar el diseño de Open Food Facts, ser adaptable a móvil y mantener el foco dentro del modal.
- `frontend/src/lib/ui/makeItBetter.ts` aplica una sustitución por cada recomendación seleccionada, sin tocar las no seleccionadas.
- `frontend/src/lib/ui/makeItBetter.test.ts` cubre los casos sin cambios, con una única selección y con varias selecciones.

## Pruebas automatizadas

Ejecuta las pruebas específicas desde la raíz:

```bash
cd server
uv run --extra dev pytest -q tests/test_make_it_better_api.py

cd ../frontend
pnpm check
pnpm test
pnpm build
```

Las pruebas del backend validan que se elige la mejor alternativa catalogada. Las del frontend confirman que una receta no cambia sin selecciones y que sólo se sustituyen los productos elegidos.
