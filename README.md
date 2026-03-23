# Trascrizione MP3/MP4 Offline (faster-whisper)

Script CLI: `transcription_cli.py`  
GUI desktop: `transcription_gui.py`  
Funziona in locale (offline) e salva la trascrizione in un file `.txt`.

## Requisiti

```bash
pip install faster-whisper numpy PySide6
```

Per creare l'eseguibile macOS:

```bash
pip install pyinstaller
```

## Uso GUI (consigliato)

Avvia l'interfaccia desktop:

```bash
python3 transcription_gui.py
```

Dalla GUI puoi:
- caricare file MP3/MP4 con `drag & drop` oppure pulsante
- scegliere affidabilita' `Alta`, `Media`, `Bassa`
- vedere il `modello in uso` in base al preset selezionato
- vedere/aprire il percorso della cartella modelli
- verificare la presenza del modello con `Verifica modelli` e scaricarlo se manca
- scaricare la trascrizione direttamente dall'app (pulsante `Scarica trascrizione`)
- bloccare l'avvio della trascrizione se il modello selezionato non e' disponibile

Mappatura affidabilita' (come i 3 profili del README):
- `Alta` -> `--model large-v3 --mode accurate`
- `Media` -> `--model small --mode balanced`
- `Bassa` -> `--model base --mode fast`

## Uso CLI

Se nella cartella c'e' un solo file supportato (`.mp3` o `.mp4`):

```bash
python3 transcription_cli.py
```

Output: file `.txt` con lo stesso nome del file audio.

### Comandi utili

Trascrizione veloce:

```bash
python3 transcription_cli.py --model base --mode fast --lang it
```

Trascrizione bilanciata:

```bash
python3 transcription_cli.py --model small --mode balanced --lang it
```

Trascrizione piu' accurata:

```bash
python3 transcription_cli.py --model large-v3 --mode accurate --lang it
```

## Parametri principali CLI

- `--input "file.mp3|file.mp4"`: specifica il file audio/video
- `--output "output.txt"`: specifica il file di output
- `--lang it`: lingua (es. `it`, `en`)
- `--prompt "testo"`: contesto per migliorare termini specifici
- `--model tiny|base|small|medium|large-v3`: modello
- `--mode fast|balanced|accurate`: preset velocita'/qualita'
- `--model-cache-dir "./models/faster-whisper"`: cartella modelli locali
- `--local-files-only`: usa solo modelli gia' scaricati

## Build eseguibile macOS (.app)

Dal root del progetto (usa lo spec che include icona `.icns` e `app_icon.png`):

```bash
PYINSTALLER_CONFIG_DIR=.pyinstaller python3 -m PyInstaller -y faster_whisper_transcriber.spec

mkdir -p "dist/Faster Whisper Transcriber.app/Contents/Frameworks/models"
cp -R "models/faster-whisper" "dist/Faster Whisper Transcriber.app/Contents/Frameworks/models/faster-whisper"
rm -rf "dist/Faster Whisper Transcriber.app/Contents/Frameworks/models/faster-whisper/.locks"
codesign --force --deep --sign - "dist/Faster Whisper Transcriber.app"
```

Output:
- app bundle: `dist/Faster Whisper Transcriber.app`
- cartella eseguibile: `dist/FasterWhisperTranscriber/`

Note:
- I modelli presenti in `models/faster-whisper` vengono copiati nel bundle e usati offline.
- Se un modello non e' incluso, usa il pulsante `Verifica modelli` per scaricarlo in `~/Library/Application Support/faster_whisper_transcriber/models/faster-whisper`.
- Al primo avvio macOS potrebbe bloccare l'app (Gatekeeper). Se succede, aprila con click destro -> Apri.
- Se distribuisci a terzi, valuta signing/notarization Apple.
