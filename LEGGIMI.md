# Archivio fonti – guida all'installazione

Un archivio personale che si riempie da solo ogni 3 ore con comunicati, avvisi e notizie delle fonti che scegli, e che consulti da una pagina web con ricerca e filtri.

Serve solo un account GitHub gratuito. La prima volta conviene farlo dal computer (dieci minuti circa); dopo, la pagina si consulta anche dal telefono.

---

## 1. Crea l'account e lo spazio

1. Vai su **github.com** e registrati (gratis).
2. In alto a destra: **+ → New repository**.
3. Nome: `archivio-fonti`. Lascia **Public** (serve per la pagina gratuita). Clicca **Create repository**.

## 2. Carica i file

1. Nella pagina del repository clicca **uploading an existing file**.
2. Trascina dentro **tutto il contenuto** della cartella `archivio-fonti` (i file `raccogli.py`, `fonti.yaml`, `requirements.txt`, `LEGGIMI.md` e la cartella `docs`).
3. Clicca **Commit changes**.

La cartella `.github` è nascosta e spesso il caricamento la salta. Controlla: se nel repository non vedi `.github`, creala così:

1. **Add file → Create new file**.
2. Come nome scrivi esattamente: `.github/workflows/aggiorna.yml`
3. Incolla dentro il contenuto del file `aggiorna.yml` che trovi nel pacchetto (`.github/workflows/aggiorna.yml`).
4. **Commit changes**.

## 3. Accendi la pagina web

1. **Settings → Pages**.
2. Alla voce *Branch* scegli `main` e la cartella `/docs`, poi **Save**.
3. Dopo un minuto la pagina è online all'indirizzo
   `https://TUONOME.github.io/archivio-fonti/`
   Salvala tra i preferiti del telefono (su iPhone: Condividi → Aggiungi alla schermata Home).

## 4. Primo giro dei raccoglitori

1. Scheda **Actions**. Se chiede conferma, clicca il pulsante verde per abilitare i workflow.
2. A sinistra scegli **Aggiorna archivio**, poi **Run workflow → Run workflow**.
3. Dopo qualche minuto il pallino diventa verde: ricarica la pagina, l'archivio è pieno.

Da qui in poi gira da solo ogni 3 ore.

---

## Usare l'archivio

- **Ricerca**: scrivi una o più parole (es. `ospedale Iglesias`). Trova le voci che le contengono tutte, nel titolo o nel testo. Gli accenti non contano.
- **Sezioni** e **fonti**: per restringere il campo.
- **Solo con testo completo**: mostra solo le voci di cui è salvato il testo integrale (comunicati e pagine istituzionali).
- Tocca un **titolo** per aprire il testo e i pulsanti *Apri originale*, *Copia testo*, *Copia citazione*, *Copia link*.
- **Stato delle fonti**: dice quali fonti funzionano e quali sono in errore.

## Aggiungere o togliere fonti

Si fa tutto nel file `fonti.yaml`: aprilo su GitHub, clicca la matita, modifica, **Commit changes**. Le istruzioni sono scritte in cima al file. Tre modi:

- `tipo: google` + `cerca:` → la soluzione più semplice e robusta. `site:nomesito.it` prende tutto quello che Google trova di quel sito.
- `tipo: rss` + `url:` → se il sito ha un feed.
- `tipo: pagina` + `url:` (+ `filtro:`) → per i siti senza feed: legge la pagina dei comunicati.

Se una fonte resta in errore per giorni, di solito il sito ha cambiato indirizzo: correggi l'`url`. Il Comune di Iglesias ha annunciato un nuovo sito: quando cambierà, quelle due fonti andranno aggiornate.

## Cosa salva e cosa no

- Per enti, istituzioni, partiti e società salva il **testo completo** (dove indicato `testo: si`).
- Per i **giornali** salva solo titolo, data e link: l'articolo si legge sul sito della testata.
- I siti che chiedono di non essere letti da programmi (robots.txt) vengono rispettati: di quelli resta titolo e link.
- L'archivio conserva le ultime 8.000 voci.

## Se qualcosa non va

- **Il workflow fallisce al momento di salvare** (“Permission denied”): Settings → Actions → General → *Workflow permissions* → **Read and write permissions** → Save.
- **La pagina è vuota**: controlla che il primo giro in Actions sia andato a buon fine.
- **Una fonte mostra 0 trovate**: con `tipo: google` può succedere se Google non indicizza quel sito; prova una ricerca per nome, es. `cerca: '"Comune di Carbonia"'`.
