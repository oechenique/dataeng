# The Data Foundry — portfolio de Data Engineering

Sitio estático (HTML/CSS puro, sin frameworks) — se despliega sin ningún build.

## Cómo subirlo a GitHub

```bash
cd site
git init
git add .
git commit -m "sitio inicial"
gh repo create tu-usuario/data-engineering-site --public --source=. --push
```

(o creá el repo vacío en github.com y hacé `git remote add origin ...` + `git push`)

## Cómo conectarlo a Vercel

1. Entrá a vercel.com, iniciá sesión con tu cuenta de GitHub.
2. "Add New Project" → elegí el repo recién creado.
3. Framework Preset: dejalo en "Other" (no hace falta build command, es HTML puro).
4. Deploy. Vercel te da un dominio tipo `tu-proyecto.vercel.app` al toque.
5. (Opcional) Settings → Domains, agregás tu dominio propio si tenés uno.

Cada push a `main` desde ahora en más se deploya solo.

## Estructura

```
index.html                       — home
proyectos/medallion-pipeline.html — case study 1 (listo)
proyectos/asesor-turismo.html     — case study 2 (listo)
css/style.css                     — estilos compartidos
js/script.js                      — terminal animada (data-lines) + theme toggle
```

## Pendiente

- Agregar `proyectos/data-lake-athena.html`
- Sumar el masterhead pixel art como imagen de fondo o accent en el hero (opcional)
