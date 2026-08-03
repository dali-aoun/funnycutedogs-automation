# FunnyCuteDogs — Pipeline d'automatisation YouTube

Automatise le montage et la publication des vidéos de la chaîne `@funnycutedogs`.
Sourcing des clips = manuel (toi). Montage + upload = automatisé, gratuit
(GitHub Actions + FFmpeg + YouTube Data API v3).

## Setup initial (une seule fois)

1. `pip install -r requirements.txt` en local
2. `python scripts/get_refresh_token.py` — ouvre ton navigateur, tu autorises
   l'accès à ta chaîne YouTube, le script affiche 3 valeurs à copier
3. Va dans **Settings > Secrets and variables > Actions** du repo GitHub et
   ajoute 3 secrets :
   - `YOUTUBE_CLIENT_ID`
   - `YOUTUBE_CLIENT_SECRET`
   - `YOUTUBE_REFRESH_TOKEN`

## Publier une nouvelle vidéo

1. Crée un dossier `videos/<nom-du-theme>/`
2. Mets tes clips bruts dans `videos/<nom-du-theme>/clips/` (nommés
   `01.mp4`, `02.mp4`, ... dans l'ordre de montage souhaité)
3. Ajoute la narration dans `videos/<nom-du-theme>/narration.mp3`
   (musique de fond optionnelle : `music.mp3`)
4. Crée `videos/<nom-du-theme>/meta.json` (titre, description, tags) — copie
   `videos/zoomies/meta.json` comme modèle
5. Push sur GitHub, puis va dans l'onglet **Actions** → workflow
   **"Render and upload video"** → **Run workflow** → indique le nom du
   dossier (ex: `zoomies`) → Run

Le workflow assemble la vidéo avec FFmpeg (clips + narration + watermark)
et la publie automatiquement sur YouTube.

## Watermark de chaîne (optionnel)

Place un logo PNG transparent dans `assets/logo_watermark.png` — il sera
incrusté en bas à droite de chaque vidéo automatiquement.

## Tester le montage en local (sans publier)

```
python scripts/assemble_video.py videos/zoomies
```

Génère `videos/zoomies/final.mp4` que tu peux visionner avant de publier.
