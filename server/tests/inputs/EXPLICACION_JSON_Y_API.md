# Qué son los JSON y la API de este proyecto

## Resumen corto

El proyecto **no almacena ni copia una web**. Es una API local: recibe una receta que ya se ha analizado, consulta archivos JSON que están en esta carpeta y devuelve un resultado en JSON para que la interfaz lo pinte en su tabla.

La ruta del flujo es:

```text
Texto/URL de receta → parser de receta → tabla de ingredientes → API local → respuesta JSON → interfaz/PDF
```

Esta carpeta contiene la parte situada en medio: los datos y la API. Ahora también incluye una demostración visual aislada en `frontend-demo/`. No es el frontend original de la aplicación: sirve para probar el botón mientras se integra en el cliente real.

## Los archivos JSON existentes

| Archivo | Qué contiene | Para qué se usa |
| --- | --- | --- |
| `ingredients.full.json` | Una taxonomía reducida de 20 ingredientes de Open Food Facts: identificador, nombre en varios idiomas, sinónimos y relaciones padre/hijo. | Reconocer `pera`, `pear`, `red wine`, etc. y devolver un identificador común como `en:pear`. |
| `labels.full.json` | 26 etiquetas/certificaciones, por ejemplo las relacionadas con producción ecológica. | Buscar y mostrar nombres de etiquetas mediante `/labels/search`. |
| `make_it_better_catalog.json` | Catálogo explícito de productos, Nutri-Score, Green-Score y alternativas permitidas. | Buscar la mejor mejora para el botón Make it better. |
| `frontend-demo/` | Mini frontend estático de prueba (`index.html`, `app.js`, `styles.css`). | Ver y probar el botón sin disponer del frontend real. |

Un JSON es simplemente texto estructurado. Por ejemplo, en `ingredients.full.json`, `en:pear` es una clave estable y dentro tiene los nombres `pear`, `pera`, etc. No significa que el proyecto tenga una pera física ni que esté guardando la receta del usuario.

## Qué hace `api.py`

`api.py` crea un servidor FastAPI. Cuando arranca lee los JSON una vez, verifica que las relaciones entre ingredientes no estén rotas y crea índices para buscar rápido aunque el usuario escriba mayúsculas o acentos distintos.

Sus rutas son:

| Ruta | Entrada | Resultado |
| --- | --- | --- |
| `GET /health` | Nada | Confirma que los JSON han cargado y da el número de registros. |
| `POST /scan-recipe` | Lista de ingredientes ya extraídos. | Separa los reconocidos, los no reconocidos y las sugerencias basadas en taxonomía. |
| `GET /ingredients/{id}` | Un id como `en:pear`. | Devuelve la ficha del ingrediente. |
| `GET /labels/search` | Texto a buscar. | Devuelve etiquetas del JSON que coinciden. |
| `POST /make-it-better/check` | Productos de la tabla principal. | Devuelve la mejor mejora de Nutri-Score, Green-Score o ambas. |

Ejemplo de lo que la interfaz manda para reconocer ingredientes:

```json
{
  "ingredients": ["pera", "red wine", "mystery powder"],
  "language": "es"
}
```

La API no inventa que `mystery powder` es un ingrediente conocido: lo devuelve en `unresolved_ingredients`. Esta decisión evita resultados falsos.

## Qué no puede concluir el JSON original

Los dos JSON originales son una **taxonomía**, no un catálogo de productos ni de puntuaciones. Por tanto, con solo `ingredients.full.json` no se puede afirmar que un producto concreto tenga una mejora: faltan identificador y puntuaciones del producto.

Para comparar productos hay que guardar o consultar datos del producto concreto y explicar el criterio. La nueva función utiliza Nutri-Score y Green-Score declarados en el catálogo local; es informativa, no consejo médico ni comprobación de alergias.

## Cómo ejecutarlo y verlo

Desde esta carpeta:

```bash
source .venv/bin/activate
python -m uvicorn api:app --reload
```

Después se puede abrir `http://127.0.0.1:8000/docs`. FastAPI muestra allí cada ruta, qué JSON se debe enviar y una respuesta de ejemplo.

Para la prueba visual abre `http://127.0.0.1:8000/demo/` con el servidor iniciado.
