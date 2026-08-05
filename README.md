# FunnyCuteDogs — Pipeline d'automatisation YouTube + Instagram

Automatise le montage et la publication des vidéos de la chaîne `@funnycutedogs`
sur YouTube et Instagram (Reels). Sourcing des clips = manuel (toi). Montage +
publication = automatisé, gratuit (GitHub Actions + FFmpeg + YouTube Data API v3
+ Instagram Graph API + Cloudflare R2).

## Setup initial (une seule fois)

1. `pip install -r requirements.txt` en local
2. `python scripts/get_refresh_token.py` — ouvre ton navigateur, tu autorises
   l'accès à ta chaîne YouTube, le script affiche 3 valeurs à copier
3. Va dans **Settings > Secrets and variables > Actions** du repo GitHub et
   ajoute ces secrets :
   - `YOUTUBE_CLIENT_ID`
   - `YOUTUBE_CLIENT_SECRET`
   - `YOUTUBE_REFRESH_TOKEN`
   - `IG_ACCESS_TOKEN` (token système Meta, ne expire pas)
   - `IG_BUSINESS_ACCOUNT_ID` (compte Instagram Business lié à la Page)
   - `FB_PAGE_ID`
   - `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `R2_BUCKET`,
     `R2_PUBLIC_URL` (hébergement temporaire public requis par l'API
     Instagram, bucket R2 gratuit)

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

Le workflow :
1. assemble la vidéo horizontale avec FFmpeg (clips + narration + watermark)
2. la publie sur YouTube
3. découpe un Reel vertical 9:16 (60s, le "hook" pour driver vers la vidéo
   complète)
4. l'héberge temporairement sur Cloudflare R2, le publie sur Instagram, puis
   supprime le fichier de R2

## Watermark de chaîne (optionnel)

Place un logo PNG transparent dans `assets/logo_watermark.png` — il sera
incrusté en bas à droite de chaque vidéo automatiquement.

## Tester le montage en local (sans publier)

```
python scripts/assemble_video.py videos/zoomies
```

Génère `videos/zoomies/final.mp4` que tu peux visionner avant de publier.
