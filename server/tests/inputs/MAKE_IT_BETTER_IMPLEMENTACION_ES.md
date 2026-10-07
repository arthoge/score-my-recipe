# Implementación de «Make it better»

## Resultado

Se eliminó la versión anterior del botón de mozzarella. La nueva implementación revisa la lista enviada desde la ventana principal, busca mejoras de **Nutri-Score**, **Green-Score** o de ambos en una base de datos local y abre una modal para que el usuario decida cada cambio.

Flujo completo:

```text
Tabla principal con productos → Make it better → POST /make-it-better/check
→ modal con recipiente original y recipiente sugerido → Sí / No
→ Switch ingredient (solo tras Sí) o Next (tras No) → siguiente paso
```

No hay cambio automático. Elegir **Sí** solo muestra el botón `Switch ingredient`; el ingrediente de la tabla se sustituye únicamente al pulsar ese segundo botón. Elegir **No** conserva el original y pasa a la siguiente sugerencia.

## Carpetas y archivos modificados

| Ruta | Función |
| --- | --- |
| `api.py` | Backend: carga el catálogo, calcula la mejora más alta y expone la ruta de comprobación. También sirve la demo visual. |
| `make_it_better_catalog.json` | Base de datos local de productos, sus dos puntuaciones y alternativas permitidas. Incluye el ejemplo `yogur de chocolate`. |
| `frontend-demo/index.html` | Ventana principal de prueba y estructura de la modal con los dos recipientes. |
| `frontend-demo/app.js` | Envía la lista, muestra las puntuaciones, gestiona Sí/No y realiza el cambio solo tras `Switch ingredient`. |
| `frontend-demo/styles.css` | Diseño de la tabla, la modal y los recipientes. |
| `tests/test_api.py` | Prueba que se selecciona la mejora más fuerte y que se mantienen productos sin mejora. |

## Backend

La ruta es `POST /make-it-better/check`. Recibe productos de la tabla:

```json
{
  "ingredients": ["yogur de chocolate", "tomate", "harina"],
  "language": "es"
}
```

Para cada producto conocido, compara las alternativas declaradas en `make_it_better_catalog.json`. Asigna A=5, B=4, C=3, D=2 y E=1; suma las ganancias de Nutri-Score y Green-Score y devuelve **una sola** alternativa: la de mayor ganancia combinada. Si solo mejora una puntuación, devuelve esa única mejora. Si mejoran ambas, devuelve las dos.

En el ejemplo, `yogur de chocolate` (D/D) recibe como mejor opción `yogur natural ecológico` (A/A). `tomate` y `harina` no se inventan: salen en `no_improvement`.

## Frontend y modal

La demo se publica en `GET /demo/`. Tiene la tabla principal, el botón **Make it better** y **Next**. Al recibir sugerencias abre una modal que contiene:

- Recipiente original: nombre, Nutri-Score y Green-Score del producto enviado.
- Recipiente sugerido: misma información de la mejor alternativa.
- Lista explícita de las mejoras, por ejemplo `Nutri-Score: D → A`.
- Botones **Sí** y **No, mantener original**.

Después de **Sí** aparece `Switch ingredient`. Al pulsarlo, se actualiza la fila correspondiente de la tabla y se muestra la siguiente sugerencia. Con **No**, no se toca la fila y se avanza directamente. Al terminar, la modal se cierra.

## Cómo probarlo

Desde `/home/elerazo/score-my-recipe/server/tests/inputs`:

```bash
source .venv/bin/activate
python -m uvicorn api:app --reload
```

Abre `http://127.0.0.1:8000/demo/`.

1. La lista inicial contiene `yogur de chocolate`, tomate y harina.
2. Pulsa **Make it better**.
3. Comprueba que la modal muestra los dos recipientes y las dos mejoras D → A.
4. Pulsa **No, mantener original**: la modal termina y el yogur no cambia.
5. Repite la prueba, pulsa **Sí** y después **Switch ingredient**: la primera fila pasa a `Yogur natural ecológico`.
6. Edita la primera fila a un producto no catalogado y prueba otra vez: no habrá sugerencias inventadas.

Para comprobar el backend sin navegador:

```bash
.venv/bin/python -m pytest -q tests
```

## Datos pendientes para producción

El catálogo actual es un ejemplo local de integración, no una sincronización en tiempo real. Antes de producción hay que alimentar `make_it_better_catalog.json` con identificadores de producto fiables y sus Nutri-Score/Green-Score vigentes, y definir la fuente y frecuencia de actualización.
