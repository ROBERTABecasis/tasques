# 🏠 Dashboard de tasques de la llar

Dashboard online que es sincronitza amb Notion i s'actualitza sol cada dia.

## Què fa

Cada dia a les 06:00 UTC, un workflow de GitHub Actions:
1. Mira la BD "Tasques de la llar" a Notion
2. Si alguna tasca té una "Darrera vegada fet" que no està a l'Historial, la registra
3. Genera un dashboard HTML amb les estadístiques
4. Publica el dashboard a GitHub Pages (URL pública)

## Setup (10 minuts)

### 1. Revoca el token antic i crea'n un de nou

Si has compartit el token de Notion en un xat, revoca'l per seguretat:
- Ves a https://www.notion.so/my-integrations
- Selecciona la integració, revoca el token, i genera'n un de nou
- Comprova que la integració té accés a les bases de dades "Tasques de la llar" i "Historial de tasques"

### 2. Crear el repositori a GitHub

1. Ves a https://github.com/new
2. Nom del repo: `dashboard-llar` (o el que vulguis)
3. **Privat** (recomanat, perquè el dashboard mostrarà dades vostres)
4. Crea el repo
5. Puja **tots els fitxers d'aquesta carpeta** al repo (els pots arrossegar des de la web de GitHub: "uploading an existing file")

### 3. Configurar el secret

1. Al repo, ves a **Settings → Secrets and variables → Actions**
2. Clic a **New repository secret**
3. Nom: `NOTION_TOKEN`
4. Valor: el teu token de Notion (`ntn_...`)
5. **Add secret**

### 4. Activar GitHub Pages

1. Al repo, ves a **Settings → Pages**
2. A "Source", selecciona **GitHub Actions**
3. Guarda

### 5. Llençar la primera execució

1. Ves a la pestanya **Actions** del repo
2. Selecciona "Sync i publica dashboard"
3. Clic a **Run workflow → Run workflow**
4. Espera 30 segons que acabi

### 6. Veure el dashboard

La URL serà: `https://[el-teu-usuari].github.io/dashboard-llar/`

(La trobaràs també a Settings → Pages quan estigui desplegada.)

Pots desar la URL a la pantalla d'inici del mòbil com una app.

## Si has fet servir noms diferents

Si has reanomenat les bases de dades o algunes columnes, edita `sync_and_render.py`:
- `TASKS_DS_ID` i `HISTORIAL_DS_ID`: IDs de les data sources
- Els noms de propietats (`Tasca`, `Darrera vegada fet`, `Qui ho ha fet per ultim cop`, `Tasca feta`, `Data`, `Qui`)

## Executar localment per provar

```bash
export NOTION_TOKEN="ntn_..."
python sync_and_render.py
# obre index.html al navegador
```
