# FunnyCuteDogs — Pipeline d'automatisation YouTube + Instagram

Chaîne 100% automatisée pour `@funnycutedogs` : sourcing des clips, narration,
montage et publication sur YouTube + Instagram (Reels), sans intervention
manuelle. Entièrement gratuit (GitHub Actions + FFmpeg + Pexels API + Edge TTS
+ YouTube Data API v3 + Instagram Graph API + Cloudflare R2).

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
   - `PEXELS_API_KEY` (clé gratuite sur [pexels.com/api](https://www.pexels.com/api/),
     sourcing automatique des clips vidéo libres de droits)

## Publier une nouvelle vidéo

1. Crée un dossier `videos/<nom-du-theme>/`
2. Crée `videos/<nom-du-theme>/meta.json` — copie `videos/zoomies/meta.json`
   comme modèle. Il contient tout ce dont le pipeline a besoin :
   - `title`, `description`, `tags`, `privacyStatus` → métadonnées YouTube
   - `script` → texte narré, converti en voix off automatiquement
   - `keywords` → termes de recherche pour trouver des clips libres de droits
   - `numClips` → nombre de clips à assembler (8 par défaut)
3. Push sur GitHub, puis va dans l'onglet **Actions** → workflow
   **"Render and upload video"** → **Run workflow** → indique le nom du
   dossier (ex: `zoomies`) → Run

Le workflow :
1. télécharge des clips libres de droits depuis Pexels (mots-clés du `meta.json`)
2. génère la narration à partir du `script` (voix neuronale gratuite Edge TTS)
3. assemble la vidéo horizontale avec FFmpeg (clips + narration + watermark)
4. la publie sur YouTube
5. découpe un Reel vertical 9:16 (60s, le "hook" pour driver vers la vidéo
   complète)
6. l'héberge temporairement sur Cloudflare R2, le publie sur Instagram, puis
   supprime le fichier de R2

Apporter tes propres clips/narration reste possible : il suffit de déposer
`clips/*.mp4` et `narration.mp3` toi-même, le pipeline ne les régénère que
s'ils sont absents.

## Publication automatique espacée (file d'attente)

`videos/queue.txt` liste les slugs à publier, un par ligne, dans l'ordre.
Le workflow **"Scheduled publish"** tourne automatiquement Mardi, Jeudi et
Dimanche à 15h UTC : il dépile la première ligne de la queue, publie cette
vidéo (YouTube + Instagram), retire la ligne et commit la queue mise à jour.
Zéro intervention manuelle — il suffit d'ajouter des slugs à `queue.txt` (et
leur `meta.json` correspondant) pour garder le rythme de publication.

## Watermark de chaîne (optionnel)

Place un logo PNG transparent dans `assets/logo_watermark.png` — il sera
incrusté en bas à droite de chaque vidéo automatiquement.

## Tester le montage en local (sans publier)

```
python scripts/assemble_video.py videos/zoomies
```

Génère `videos/zoomies/final.mp4` que tu peux visionner avant de publier.
